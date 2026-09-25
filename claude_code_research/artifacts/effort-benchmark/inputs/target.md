# Plan — Per-Key Rate Limiting with Burst Allowance and Graceful Degradation (gatewaysvc)

Owner: Platform Edge
Status: Proposed
Target release: gatewaysvc v2.14
Reviewers: Edge, SRE, API Platform

---

## Context

`gatewaysvc` is the shared HTTP API gateway that fronts all external traffic for the
public API. It terminates TLS, authenticates the caller's API key, resolves a route
from the routing table, and proxies to a backend service. It currently has **no
request-rate enforcement of any kind**. The only backpressure available today is
per-backend connection pool saturation, which manifests as 502s from the gateway
long after the backend has already degraded.

Three incidents in the last quarter motivated this work:

- **INC-4412 (2026-05-19)** — an integration partner's retry loop with no backoff drove
  41k req/min at `POST /v1/documents/render` for 22 minutes. The render backend's queue
  grew unbounded; p99 for *all* callers went from 180ms to 14s. Mitigated by a manual
  `iptables` rule 31 minutes in.
- **INC-4508 (2026-06-30)** — a customer batch job saturated the shared Postgres pool
  behind `/v1/search`. Two unrelated tenants saw sustained 5xx.
- **INC-4571 (2026-07-24)** — a load test misconfigured to point at production. No
  mechanism existed to cap it.

Every fix was manual, took over 20 minutes, and was blunt (whole-IP blocks).

### Goals

1. Enforce a **per-API-key** request rate with a configurable **burst allowance**.
2. Support **per-route** and **global** limits, with well-defined interaction.
3. Work across the fleet (8 pods per region, 3 regions), not just per-process.
4. Degrade gracefully when the limiter backend is unavailable.
5. Emit standards-shaped client headers so integrators can self-throttle.

### Non-goals

- Long-window quotas (daily/monthly). Billing's concern, tracked in PLAT-2290.
- Concurrency limiting (max in-flight per key) — different failure mode, not merged in.
- Adaptive limits driven by backend health. See "Deferred".
- Per-end-user limits. gatewaysvc does not see end-user identity.

### Constraints

- gatewaysvc is Go 1.24, a Kubernetes Deployment, 6 replicas per region.
- Added latency budget for the limiter path: p50 **≤ 1.5 ms**, p99 **≤ 8 ms**.
- Existing Redis 7.2 cluster (`edge-redis`, 3 shards, 1 replica each) at ~18% CPU
  headroom can absorb this load.
- No new dependencies beyond `github.com/redis/go-redis/v9`, already vendored.

---

## Design decisions

### D1 — Algorithm: token bucket

**Decision:** Token bucket, one bucket per (scope, identity) pair, with lazy refill
computed from elapsed time on each access.

**Rationale.** Three candidates were considered.

| Algorithm | Burst support | State per identity | Boundary fairness | Verdict |
|---|---|---|---|---|
| Fixed window counter | Poor — 2x burst at window edges | 1 int + TTL | Bad | Rejected |
| Sliding window log | Exact | O(rate × window) timestamps | Excellent | Rejected — memory |
| Sliding window counter | Approximate | 2 ints + TTL | Good | Rejected — no burst semantics |
| **Token bucket** | **First-class** | **2 ints + TTL** | **Good** | **Chosen** |

- **Fixed window** is rejected for the boundary doubling problem: a client at 100 req/s
  can send 100 requests in the last 10ms of one window and 100 more in the first 10ms
  of the next — a 200 req/s spike. That spike is exactly what blew up INC-4412.
- **Sliding window log** is exact but stores one timestamp per request in the window.
  At the partner tier (1000 req/s, 1s window) that is 1000 entries per key in Redis
  with an O(n) trim. Rejected on memory and CPU.
- **Sliding window counter** is cheap and reasonably fair but has no notion of burst
  allowance separable from the sustained rate. We explicitly sell those as two knobs.
- **Token bucket** gives exactly those two knobs — `refill_rate_per_sec` and
  `capacity` — stores two values per identity, refills lazily (no sweeper), and is
  trivially expressible as an atomic Redis Lua script.

**Refill is lazy, not scheduled.** No goroutine or Redis job walks buckets to add
tokens. On each access we compute:

```
elapsed_ms = now_ms - last_refill_ms          # clamped to >= 0
refilled   = tokens + (elapsed_ms * refill_rate_milli_per_ms) / 1000
tokens'    = min(capacity_milli, refilled)
```

An idle bucket costs nothing until touched, and buckets can be evicted by TTL without
correctness loss — a missing bucket is indistinguishable from a full bucket (D6).

**Fixed-point arithmetic.** Token counts are stored as **millitokens** (`int64`),
1 token == 1000 millitokens. Redis Lua numbers are IEEE-754 doubles and we refuse to
depend on float rounding for an admission decision; all arithmetic in
`ratelimit_take.lua` is integer arithmetic over millitokens.

### D2 — Storage backend: in-memory first, Redis-backed as the production target

**Decision:** Define a `Store` interface with two implementations. Ship the in-memory
implementation first (Phase A), then the Redis implementation (Phase B), and keep
both permanently — the in-memory store is not scaffolding, it is the degraded-mode
fallback (see D5).

**Rationale.**

- A purely **in-memory** limiter is per-pod. With 8 pods per region, a key configured
  at 100 req/s could sustain up to 800 req/s if its traffic spreads evenly, or be
  throttled to 12.5 req/s if it all lands on one pod. Neither is acceptable.
- A **Redis-backed** limiter gives one shared bucket per identity fleet-wide, which is
  the semantics we sell. Cost is one round trip per request per scope; measured RTT to
  `edge-redis` from a gateway pod is p50 0.4ms, p99 2.1ms — within budget once the
  scope lookups are pipelined (D4).
- Building both is cheap: the algorithm lives in `bucket.go` and is shared; the stores
  differ only in how they load, mutate, and persist the two integers.

**Migration path (in-memory → Redis).** The cutover is not a flag flip. Three stages,
each independently reversible:

1. **`memory`** — in-memory store only. Limits are per-pod. Phase A and dev.
2. **`redis_shadow`** — every request is evaluated against *both* stores. The in-memory
   decision is authoritative and enforced; the Redis decision is computed, recorded to
   metrics, and reported only in `X-RateLimit-Shadow-Decision`. Validates Redis
   correctness and latency under real traffic with no risk of wrongly rejecting anyone.
3. **`redis`** — Redis is authoritative. The in-memory store is still constructed and
   used only when the circuit breaker is open (degraded mode).

The mode is one hot-reloadable config key, `ratelimit.store.mode` (Phase C). Rolling
back from `redis` to `memory` needs no restart and no data migration — bucket state is
disposable by construction (D1).

### D3 — Scope precedence and enforcement

Three limit **scopes** exist:

| Scope | Identity | Purpose |
|---|---|---|
| `key` | authenticated API key id, or `anon:<client_ip>` | Per-caller fairness |
| `route` | route id from the routing table, e.g. `documents.render` | Protect one backend |
| `global` | the literal string `default`, per region | Protect the gateway itself |

**Decision:** Enforcement is **conjunctive**; configuration resolution is by
**specificity**. These are two separate mechanisms and are frequently confused, so
they are stated separately.

**Enforcement (conjunctive).** A request is admitted only if *every* configured scope
in its chain admits it. There is no "most specific wins" at enforcement time — a
per-key limit of 1000 req/s does not entitle a caller to exceed the route's 500 req/s
limit. Route and global limits exist to protect shared resources, and a per-key grant
must not override a shared-resource guard.

**Evaluation order:** `route` → `key` → `global` (most specific first). Order matters
because (a) most denials are at the `key` scope, so evaluating it first minimises
wasted work, and (b) header attribution (D7) depends on which scope denied first.

**Refund invariant.** Scopes are separate buckets, and a request that is denied at one
scope has still consumed tokens from every other scope that admitted it. Those must be
returned, or a caller repeatedly blocked by the global limit would also be silently
drained at the key scope and stay throttled after the global pressure subsided.
Invariants:

- **INV-1** — A request is admitted only if every scope in its resolved chain admits it.
- **INV-2** — Scopes are evaluated most-specific first: `key`, then `route`, then `global`.
- **INV-3** — If any scope denies, every token consumed by *any other* scope during
  that same request is refunded before the response is written. The denying scope
  itself consumed nothing and is not refunded.
- **INV-4** — A refund never raises a bucket above its `capacity_milli`.
- **INV-5** — A request consumes exactly `cost` tokens from each scope it is evaluated
  against; `cost` defaults to `1` and is configurable per route.
- **INV-6** — The clock used for refill is the *store's* clock, never the caller's.
  For the Redis store this is `redis.call('TIME')` evaluated inside the Lua script;
  for the memory store it is a monotonic reading taken inside the store's own lock.

INV-3 puts the refund on the *denial* path only, so it never sits in the hot path of an
admitted request. Because all scopes are evaluated in one batch (D4) rather than
short-circuited, a denial at any scope can leave up to two other buckets to refund.

**Configuration resolution (specificity).** Independently of enforcement, the
*parameters* for a given scope are resolved by walking from most specific to least
specific and taking the first defined value, per field:

```
key scope   : keys.<key_id>            → tiers.<tier_of_key>   → tiers.standard
route scope : routes.<route_id>.limit  → defaults.route
global scope: global                   (no override; exactly one definition)
```

Resolution is **per field**, not per block: a `keys.<key_id>` override that sets only
`burst_multiplier` inherits `rate_per_sec` from its tier. Operators never have to
restate a full block to change one number.

**Disabling a scope.** Setting a scope's `rate_per_sec` to `0` disables that scope
entirely — the bucket is neither consulted nor created. It does **not** mean "deny
everything"; that would make a typo catastrophic. To deny all traffic for a key, set
`keys.<key_id>.enabled: false`, which is explicit.

### D4 — Batching the scope lookups

**Decision:** For the Redis store, the three scope operations go out as one pipelined
round trip (one `EVALSHA` per scope in one pipeline), not three sequential round trips.

**Rationale.** Three sequential RTTs at p99 2.1ms would consume 6.3ms and blow the 6ms
p99 budget on their own. One pipeline is one RTT. The cost is that we cannot
short-circuit on a `key`-scope denial, so a denied request consumes tokens from every
scope that admitted it and then refunds up to two of them (INV-3). Acceptable: denials
are the rare path and the refund is itself pipelined.

This does not weaken INV-2. Evaluation order is still `key` → `route` → `global` for
attribution and refunds — the pipeline preserves reply ordering and `Limiter.decide`
walks the replies in that order. Only the *network* work is concurrent.

**Atomicity.** Each individual bucket operation is atomic (one Lua script, one key).
The three-scope decision as a whole is deliberately **not** atomic: a cross-slot
MULTI/EXEC would require all three keys in one hash slot, defeating sharding and
putting every request for a region on one Redis shard. The observable consequence is a
small over-admission window — a request can consume a route token, be denied at the
global scope, and another request can observe the route bucket in that transient state
before the refund lands. Measured in the Phase B load test this was under 0.4% of the
configured rate. Rate limits are a throttle, not a transactional ledger.

### D5 — Behaviour under backend failure: degrade, not fail-open

**Decision:** Three configurable behaviours, with **`degrade`** as the default.

| Mode | Behaviour when the Redis store is unavailable |
|---|---|
| `open` | Admit everything. No limiting at all. |
| `closed` | Deny everything with 429. |
| `degrade` | Fall back to the in-memory store with **derated** per-pod limits. |

`closed` is never a sensible default for a gateway: a Redis outage would become a total
public API outage. `open` is the common industry default but leaves us with no
protection during exactly the kind of event (infrastructure stress) where we most want
it — the INC-4412 condition.

**`degrade`** keeps enforcing, locally. Each pod falls back to its in-memory store with
the configured rate divided across the fleet:

```
derated_rate_per_sec  = ceil(rate_per_sec  / node_count_hint)
derated_capacity      = ceil(capacity      / node_count_hint)
```

`node_count_hint` is a static config value (`ratelimit.degraded.node_count_hint`,
default `8`, matching our per-region replica count). With the `standard` tier
(100 req/s sustained, capacity 200):

```
derated_rate_per_sec = ceil(100 / 8) = 13
derated_capacity     = ceil(200 / 8) = 25
```

Fleet-wide this admits at most `8 × 13 = 104` req/s against a nominal 100 req/s — a 4%
overshoot from the ceiling, accepted in exchange for never under-admitting a compliant
caller on a lightly loaded pod. Under uneven load the effective limit is lower than
nominal, which is the correct bias during an infrastructure incident.

**Circuit breaker.** The Redis store is wrapped in a breaker so we do not pay the
timeout on every request during an outage:

- `redis.timeout_ms: 50` — per-operation deadline. Exceeding it counts as a failure.
- Rolling window of the last `200` operations.
- **Open** when ≥ `40` of the last `200` operations failed (20% error rate) *and* at
  least `20` operations have been observed since the process started.
- While open: skip Redis entirely, serve from the derated in-memory store.
- **Half-open** after `5s`: allow `3` probe operations. All 3 succeed → closed.
  Any probe fails → open again for another `5s`.

The breaker is per-pod, not shared — a shared breaker would itself depend on the
failing backend.

**Transition hygiene.** When the breaker closes and Redis becomes authoritative again,
in-memory buckets are **not** merged back into Redis; they are reset to full. Replaying
local consumption would require a cross-pod merge with no consistent point in time to
merge at, and would punish callers for an outage that was ours. Over-admission for at
most one refill window (≤ 3s at the slowest configured tier) after recovery is the
accepted cost, recorded as `gatewaysvc_ratelimit_degraded_recovery_total`.

### D6 — Missing bucket means full bucket

A read of a bucket key that has expired or never existed returns nil, and the store
treats that as `tokens = capacity`. This is the only defensible default: TTL eviction
is a normal event for an idle caller (D1), and treating eviction as "empty bucket"
would throttle callers precisely because they had been quiet.

**TTL.** Every bucket key is written with

```
ttl_seconds = ceil(capacity / refill_rate_per_sec) + idle_grace_seconds
```

where `ratelimit.store.idle_grace_seconds` defaults to `60`. The first term is the time
for an empty bucket to refill completely — past that point the stored state is
informationally identical to "absent". The grace term is slack against clock skew and
against a key being touched right before expiry. Worked values for the shipped
defaults:

| Scope / tier | `rate_per_sec` | `capacity` | `ceil(cap/rate)` | TTL |
|---|---|---|---|---|
| `tiers.anonymous` | 5 | 10 | 2 | 62s |
| `tiers.trial` | 10 | 30 | 3 | 63s |
| `tiers.standard` | 100 | 200 | 2 | 62s |
| `tiers.partner` | 1000 | 2000 | 2 | 62s |
| `defaults.route` | 500 | 750 | 2 | 61s |
| `global` | 5000 | 6000 | 2 | 62s |

The TTL is refreshed with `PEXPIRE` on every write inside the same Lua script, so an
actively used bucket never expires mid-flight.

### D7 — Client-facing headers and error responses

**Decision:** Emit IETF-draft-shaped `RateLimit-*` headers on **every** proxied
response (both admitted and denied), plus `Retry-After` on denials only.

Headers on an **admitted** request:

```
RateLimit-Limit: 100
RateLimit-Remaining: 87
RateLimit-Reset: 2
RateLimit-Policy: 100;w=1;burst=200
X-RateLimit-Scope: key
X-RateLimit-Mode: enforce
```

Exact value derivations for each header are in the "Header reference" table under
Schema. `RateLimit-Policy`'s `w` is always `1` because our rate is per second.

**Attribution rule.** On an admitted request the attributed scope is the one with the
lowest *fractional* headroom, `argmin(tokens_milli / capacity_milli)`. Ties break by
evaluation order (INV-2): `key` over `route` over `global`. This tells the client which
limit they are closest to, the only number actionable for them. On a denied request the
attributed scope is the first scope, in evaluation order, that denied.

Response to a **denied** request:

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
RateLimit-Limit: 100
RateLimit-Remaining: 0
RateLimit-Reset: 2
RateLimit-Policy: 100;w=1;burst=200
Retry-After: 1
X-RateLimit-Scope: key
X-RateLimit-Mode: enforce

{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded for API key. Retry after 10ms.",
    "scope": "key",
    "retry_after_ms": 10,
    "limit": 100,
    "burst": 200,
    "request_id": "01J9ZC7QK4M2RB8VYX3TDN6H0P"
  }
}
```

- Status is **429**, never 503. 503 signals gateway unavailability and would trigger
  client retry-storm heuristics and our own SLO alerting.
- `Retry-After` is in **seconds** (integer, per RFC 9110), `ceil(retry_after_ms / 1000)`
  with a floor of `1` — `Retry-After: 0` invites the immediate retry we are suppressing.
- `retry_after_ms` in the body carries the precise sub-second value: the time for the
  attributed bucket to accumulate `cost` tokens,
  `ceil((cost_milli - tokens_milli) * 1000 / refill_milli_per_sec)`.
- `request_id` is the existing gateway request id, unchanged.

**Shadow mode.** In `redis_shadow` store mode, or when a route is in shadow rollout,
the request is **not** denied. Instead the response carries:

```
X-RateLimit-Mode: shadow
X-RateLimit-Shadow-Decision: deny
```

and the `gatewaysvc_ratelimit_decisions_total{outcome="shadow_deny"}` counter is
incremented. No 429 is emitted and no `Retry-After` is set.

### D8 — Identity extraction

The `key` scope identity is resolved in `resolver.go`:

1. If the request authenticated successfully, use the API key's stable id
   (`key_01J...`), never the raw secret. The raw key material never reaches the
   limiter, never reaches Redis, and never reaches logs.
2. If the request is unauthenticated (public endpoints, or auth failed), use
   `anon:<client_ip>` where `client_ip` is the already-computed trusted client IP
   from the existing `X-Forwarded-For` handling, and the tier is `anonymous`.
3. Requests to `/healthz`, `/readyz`, and `/metrics` bypass the limiter entirely via
   `ratelimit.exempt_paths`. Health checks must never be throttled.

Redis key format, with a hash tag around the identity so cluster slotting spreads
identities across shards:

```
rl:v1:key:{key_01J9ZC7QK4M2RB8VYX3TDN6H0P}
rl:v1:route:{documents.render}
rl:v1:global:{default}
```

The `v1` segment lets us change the value encoding later by bumping to `v2`, which
strands the old keys to expire on their own TTL rather than requiring a migration.

---

## Phases

### Phase A — Core limiter and in-memory backend

Deliverable: a working, tested, per-pod limiter behind a default-off feature flag.
No Redis. No production enforcement.

**A1. Package skeleton.** Create `internal/ratelimit/` with:

| File | Contents |
|---|---|
| `bucket.go` | `TokenBucket` value type and the pure refill/take/refund arithmetic |
| `store.go` | `Store` interface, `TakeResult`, `Op` types |
| `store_memory.go` | `MemoryStore` — sharded map implementation |
| `limiter.go` | `Limiter`, scope chain evaluation, INV-1..INV-6 |
| `resolver.go` | config resolution (D3) and identity extraction (D8) |
| `headers.go` | header formatting and the 429 body |
| `config.go` | config structs and validation |
| `middleware.go` | `net/http` middleware wiring |

**A2. `bucket.go` — pure arithmetic.** No I/O, no clock, no locks; all inputs explicit
so it is exhaustively testable:

```go
// Refill returns the token count after advancing the bucket to nowMilli.
// All token quantities are in millitokens (1 token = 1000 millitokens).
func Refill(tokensMilli, capacityMilli, refillMilliPerSec, lastMilli, nowMilli int64) int64

// Take attempts to remove costMilli. It returns the new token count and whether
// the take succeeded. On failure the token count is returned unchanged.
func Take(tokensMilli, costMilli int64) (int64, bool)

// Refund returns costMilli tokens, clamped to capacityMilli (INV-4).
func Refund(tokensMilli, capacityMilli, costMilli int64) int64

// RetryAfterMilli returns how long until costMilli tokens are available.
func RetryAfterMilli(tokensMilli, costMilli, refillMilliPerSec int64) int64
```

`Refill` clamps `nowMilli - lastMilli` to `>= 0` so a backwards clock step cannot mint
tokens, and clamps the result to `capacityMilli`.

**A3. `store.go` — the interface both backends satisfy.**

```go
type Op struct {
    Key               string // fully-qualified store key, e.g. rl:v1:key:{key_01J...}
    CapacityMilli     int64
    RefillMilliPerSec int64
    CostMilli         int64
    TTLSeconds        int64
}

type TakeResult struct {
    Allowed         bool
    TokensMilli     int64 // remaining, after this operation
    CapacityMilli   int64
    RetryAfterMilli int64 // 0 when Allowed
}

type Store interface {
    // TakeBatch evaluates ops in order and returns one result per op, same order.
    TakeBatch(ctx context.Context, ops []Op) ([]TakeResult, error)
    // RefundBatch returns tokens for ops that were consumed but must be undone.
    RefundBatch(ctx context.Context, ops []Op) error
    // Name reports the backend for metrics labelling: "memory" or "redis".
    Name() string
}
```

**A4. `MemoryStore`.** A fixed array of `256` shards, each `struct { mu sync.Mutex;
entries map[string]entry }`, selected by `fnv32a(key) % 256`. `entry` is
`{ tokensMilli int64; lastMilli int64; expiresAtMilli int64 }`.

One background goroutine sweeps expired entries every
`ratelimit.store.memory.sweep_interval` (default `30s`), taking one shard lock at a
time so a sweep never blocks the whole store. An entry read past its `expiresAtMilli`
is treated as absent (D6) whether or not the sweeper has reached it — the sweeper is a
memory reclaimer, not a correctness mechanism.

The store is bounded by `ratelimit.store.memory.max_entries` (default `500000`). On
exceeding it, evict the shard's entry with the earliest `expiresAtMilli` and increment
`gatewaysvc_ratelimit_memory_evictions_total`. Eviction is safe by D6.

**A5. `Limiter.Allow`.** The entry point:

```go
func (l *Limiter) Allow(ctx context.Context, req Request) (Decision, error)

type Request struct {
    KeyID    string // "key_01J..." or "anon:203.0.113.7"
    Tier     string // "standard", "partner", ...
    RouteID  string // "documents.render"
    Path     string
}

type Decision struct {
    Allowed         bool
    Scope           Scope  // ScopeKey | ScopeRoute | ScopeGlobal
    Mode            Mode   // ModeEnforce | ModeShadow | ModeDegraded
    LimitPerSec     int64
    BurstCapacity   int64
    RemainingTokens int64
    ResetSeconds    int64
    RetryAfterMilli int64
}
```

Algorithm:

1. If `req.Path` matches `ratelimit.exempt_paths`, return `Allowed: true` with
   `Scope` unset and emit no headers.
2. Resolve the scope chain via `resolver.Resolve(req)` → `[]Op` in order
   `key`, `route`, `global`, omitting any scope whose resolved `rate_per_sec` is `0`
   (D3) and omitting `key` when `keys.<id>.enabled` is false (that returns a
   deny with `Scope: ScopeKey` and `RetryAfterMilli: 0` immediately). `CostMilli`
   is resolved once, from the matched route's `cost` (`defaults.route.cost` when
   unrouted), and copied onto every `Op` in the chain — the `Cost` field on
   `keys.<id>`, `tiers.<tier>`, and `global` is not consulted by this step.
3. `results, err := store.TakeBatch(ctx, ops)`.
4. Walk `results` in order. The first `!Allowed` is the denying scope.
5. If a denial occurred at index `i`, refund every *other* op whose result was
   `Allowed` — `store.RefundBatch(ctx, allowedOpsExcluding(ops, results, i))` (INV-3)
   — and build the deny `Decision` from `results[i]`.
6. If all allowed, pick the attributed scope by `argmin(TokensMilli / CapacityMilli)`
   with ties broken by index (D7) and build the allow `Decision`.

**A6. Middleware.** `ratelimit.Middleware(l *Limiter)` runs **after** the existing
auth middleware (it needs `KeyID` and `Tier`) and **before** the routing/proxy
middleware. Order in `cmd/gatewaysvc/server.go`:

```
recovery → requestid → accesslog → tls_info → auth → ratelimit → router → proxy
```

After `accesslog` so denied requests are still logged with full context; after `auth`
because identity is required; before `router` so a request to a nonexistent route still
consumes key-scope tokens — otherwise probing for 404s would be a free bypass. The
`RouteID` comes from a cheap `router.Match(req)` lookup that does not mutate request
state; on no match `RouteID` is `"__unrouted__"` and resolves to `defaults.route`.

**A7. Feature flag.** `ratelimit.enabled` (default `false` on merge). When false the
middleware is not installed at all — zero overhead, not a per-request branch.

### Phase B — Redis-backed distributed limiter

Deliverable: `RedisStore` passing the same conformance suite as `MemoryStore`, plus
the breaker and the derated fallback, still default-off in production.

**B1. `ratelimit_take.lua`.** One key, integer millitoken arithmetic, atomic:

```lua
-- KEYS[1] = bucket key
-- ARGV[1] = capacity_milli
-- ARGV[2] = refill_milli_per_sec
-- ARGV[3] = cost_milli
-- ARGV[4] = ttl_seconds
local cap    = tonumber(ARGV[1])
local rate   = tonumber(ARGV[2])
local cost   = tonumber(ARGV[3])
local ttl    = tonumber(ARGV[4])

local t   = redis.call('TIME')
local now = (tonumber(t[1]) * 1000) + math.floor(tonumber(t[2]) / 1000)

local st   = redis.call('HMGET', KEYS[1], 't', 'ts')
local toks = tonumber(st[1])
local last = tonumber(st[2])

if toks == nil or last == nil then
  toks = cap          -- D6: absent means full
  last = now
end

local elapsed = now - last
if elapsed < 0 then elapsed = 0 end          -- INV-6 guard against skew
toks = toks + math.floor((elapsed * rate) / 1000)
if toks > cap then toks = cap end

local allowed = 0
local retry   = 0
if toks >= cost then
  toks    = toks - cost
  allowed = 1
else
  retry = math.ceil(((cost - toks) * 1000) / rate)
end

redis.call('HSET', KEYS[1], 't', toks, 'ts', now)
redis.call('EXPIRE', KEYS[1], ttl)
return {allowed, toks, retry}
```

`ratelimit_refund.lua` is the mirror image: refill, add `cost_milli`, clamp to
`capacity_milli` (INV-4), write back, refresh the TTL.

Both scripts call `TIME`, which makes them non-deterministic. This requires **effects
replication**, the default since Redis 3.2 and mandatory in Redis 7.x — verified
against our Redis 7.2 cluster. `TIME` is the store's clock and therefore satisfies
INV-6; gateway pod clock skew is irrelevant to the decision.

**B2. `RedisStore.TakeBatch`.** One `redis.Pipeline`, one `EVALSHA` per op, in the
order given (D4). `SCRIPT LOAD` both scripts at startup and cache the SHAs; on
`NOSCRIPT` fall back to `EVAL` once and re-load. Per-operation deadline is
`ratelimit.redis.timeout_ms` (`50`), applied as a context deadline on the pipeline
call. A pipeline error, a deadline, or any per-op error is a breaker failure and
returns `err` from `TakeBatch` — the caller (`Limiter`) then applies D5.

**B3. `RefundBatch`.** Pipelined `EVALSHA` of `ratelimit_refund.lua`. Refund failures
are **logged and swallowed**, not surfaced: a failed refund cannot change an
already-made deny decision, and retrying it inline would add latency to the deny
path. Failures increment `gatewaysvc_ratelimit_refund_failures_total`. The worst case
is that a caller loses at most `cost` tokens, which self-heals within one refill
window (≤ 3s at the slowest tier).

**B4. Breaker + degraded fallback.** `breaker.go` implements the rolling-window
breaker from D5 (window 200, threshold 40 failures, minimum 20 samples, open 5s,
3 half-open probes). `DegradingStore` wraps a primary `Store` and a fallback `Store`:

- Breaker closed → primary. On error, record failure, then serve from fallback with
  derated ops.
- Breaker open → fallback directly, no primary call, no timeout paid.
- Breaker half-open → primary for up to 3 concurrent probes; all others go to fallback.

Derating is applied when constructing the fallback ops (D5), not stored in config.

**B5. Shadow evaluation.** In `redis_shadow` mode, `Limiter.Allow` calls the memory
store (authoritative) and the Redis store (observational) concurrently, waits for
both with a `100ms` budget on the shadow call only, and never lets the shadow path
fail the request. Divergences are counted in
`gatewaysvc_ratelimit_shadow_divergence_total{authoritative,shadow}`.

### Phase C — Config, validation, and rollout

**C1. Config loading and hot reload.** The `ratelimit` block lives in the existing
`gatewaysvc.yaml`. It is watched by the existing `fsnotify` config watcher. On
change, a fully-validated new `*Config` is built and swapped in with an
`atomic.Pointer[Config]`; in-flight requests finish against the config they started
with. An invalid config is **rejected wholesale** — the previous config stays live and
`gatewaysvc_config_reload_failures_total{component="ratelimit"}` increments. A
partial apply is never performed.

Hot-reloadable: every field except `ratelimit.enabled` and
`ratelimit.store.memory.shards`, which require a restart because they determine
whether the middleware is installed and how the shard array is allocated.

**C2. Validation rules** (all enforced at load, all fatal for the candidate config):

- `rate_per_sec >= 0` and `<= 100000` for every scope and tier.
- `burst_multiplier >= 1.0` and `<= 100.0`. A multiplier below 1.0 would give a
  capacity smaller than one second of refill, which makes burst semantics
  meaningless and makes `RateLimit-Policy` self-contradictory.
- Derived `capacity = ceil(rate_per_sec * burst_multiplier)` must be `>= 1` for any
  scope with `rate_per_sec > 0`.
- Every `keys.<id>.tier` must name a tier defined in `tiers`.
- Every `routes.<id>` must name a route present in the routing table; unknown route
  ids are a validation error, not a silent no-op.
- `store.mode` ∈ {`memory`, `redis_shadow`, `redis`}.
- `store.mode != memory` requires `redis.addrs` to be non-empty.
- `degraded.node_count_hint >= 1`.
- `redis.timeout_ms` in `[5, 500]`.

**C3. Rollout.** Five stages, each gated on the exit criteria below. `ratelimit.enabled`
goes to `true` at stage 1 and stays true; what changes is `store.mode` and the
per-route `mode`.

| Stage | Config | Scope of traffic | Exit criteria |
|---|---|---|---|
| 1 | `enabled: true`, `store.mode: memory`, all routes `mode: shadow` | staging, 100% | 48h with zero limiter-attributed 5xx; p99 added latency ≤ 1.0ms |
| 2 | same, production | production, 100%, shadow only | 72h; shadow-deny rate on `tiers.standard` < 0.5% of requests |
| 3 | `store.mode: redis_shadow` | production, 100%, shadow only | 72h; shadow divergence rate < 1%; Redis p99 op latency ≤ 3ms |
| 4 | `store.mode: redis`, `routes.documents.render.mode: enforce` | one route enforcing | 7 days; ≤ 3 support tickets attributable to the limit; no partner escalation |
| 5 | `defaults.route.mode: enforce` | all routes enforcing | steady state |

Rollback at any stage is a single config edit and a hot reload — no deploy. Stage 4→3
and 5→4 rollbacks are explicitly rehearsed in staging before stage 4 begins.

**C4. Partner communication.** Before stage 4, every key on `tiers.partner` and every
key whose stage-2/3 shadow-deny rate exceeded 0.1% gets a direct notification with
their measured peak rate, their configured limit, and the enforcement date. Keys whose
observed p99 rate exceeds their tier limit get a temporary `keys.<id>` override at
their observed p99 rounded up to the next 100 req/s, with an expiry date recorded in
the config comment. We do not enforce a limit on a caller who has never been told
about it.

### Phase D — Observability

**D1. Metrics** (Prometheus, all prefixed `gatewaysvc_ratelimit_`):

| Metric | Type | Labels |
|---|---|---|
| `decisions_total` | counter | `scope`, `outcome` (`allow`\|`deny`\|`shadow_deny`\|`exempt`), `tier`, `mode` |
| `tokens_remaining_ratio` | histogram | `scope`, `tier` — buckets `0, .05, .1, .25, .5, .75, .9, 1` |
| `backend_latency_seconds` | histogram | `backend` (`memory`\|`redis`), `op` (`take`\|`refund`) |
| `backend_errors_total` | counter | `backend`, `kind` (`timeout`\|`conn`\|`script`\|`other`) |
| `breaker_state` | gauge | `backend` — `0` closed, `1` half-open, `2` open |
| `degraded_seconds_total` | counter | — |
| `degraded_recovery_total` | counter | — |
| `shadow_divergence_total` | counter | `authoritative`, `shadow` |
| `refund_failures_total` | counter | `scope` |
| `memory_evictions_total` | counter | — |
| `config_reload_total` | counter | `outcome` (`applied`\|`rejected`) |

`tier` is deliberately included but `key_id` is deliberately **not** — per-key
cardinality would be in the hundreds of thousands. Per-key visibility comes from
structured logs and from the analytics pipeline, not from Prometheus.

**D2. Structured log fields.** Added to the existing access log line, only on
`outcome != allow`:

```
ratelimit.decision   = "deny" | "shadow_deny"
ratelimit.scope      = "key" | "route" | "global"
ratelimit.tier       = "standard"
ratelimit.key_id     = "key_01J9ZC7QK4M2RB8VYX3TDN6H0P"
ratelimit.limit      = 100
ratelimit.burst      = 200
ratelimit.retry_ms   = 10
ratelimit.mode       = "enforce" | "shadow" | "degraded"
```

Allowed requests log nothing extra — at our volume that would double access log size
for no diagnostic value.

**D3. Dashboards.** One Grafana dashboard, `gatewaysvc / rate limiting`:

- Deny rate by scope and tier (stacked, 1m rate).
- Top 20 denied `key_id` over the selected range (from the log pipeline, not Prometheus).
- Backend latency p50/p99 by backend and op.
- Breaker state timeline and cumulative degraded seconds.
- Headroom heatmap: `tokens_remaining_ratio` p10 by tier.
- Shadow divergence rate (stages 2–3 only).

**D4. Alerts.**

| Alert | Condition | Severity | Rationale |
|---|---|---|---|
| `RateLimitBackendDegraded` | `breaker_state{backend="redis"} == 2` for 2m | page | Fleet is on derated local limits |
| `RateLimitDenyRateHigh` | fleet deny rate > 2% of requests for 10m | ticket | Likely a misconfigured limit, not abuse |
| `RateLimitGlobalScopeDenying` | `rate(decisions_total{scope="global",outcome="deny"}[5m]) > 0` for 5m | page | Gateway-wide saturation |
| `RateLimitRedisLatencyHigh` | `backend_latency_seconds{backend="redis"}` p99 > 10ms for 10m | ticket | Latency budget at risk |
| `RateLimitConfigRejected` | `increase(config_reload_total{outcome="rejected"}[15m]) > 0` | ticket | Live config diverges from the repo |

`RateLimitDenyRateHigh` is a ticket rather than a page on purpose: a high deny rate
during an actual abuse event is the system working correctly, and paging on correct
behaviour trains responders to ignore the alert.

---

## Schema

### Config — `gatewaysvc.yaml`, `ratelimit` block

```yaml
ratelimit:
  enabled: true                       # bool; restart required to change
  exempt_paths:                       # []string; exact-match paths, limiter bypassed
    - /healthz
    - /readyz
    - /metrics

  store:
    mode: redis                       # enum: memory | redis_shadow | redis
    idle_grace_seconds: 60            # int; added to every bucket TTL (D6)
    memory:
      shards: 256                     # int; power of two; restart required
      max_entries: 500000             # int; total across all shards
      sweep_interval: 30s             # duration

  redis:
    addrs:                            # []string; cluster seed nodes
      - edge-redis-0.edge-redis:6379
      - edge-redis-1.edge-redis:6379
      - edge-redis-2.edge-redis:6379
    timeout_ms: 50                    # int; per-operation deadline, range [5, 500]
    pool_size_per_node: 32            # int
    key_prefix: "rl:v1"               # string; bump to strand old buckets

  breaker:
    window_size: 200                  # int; rolling operation count
    failure_threshold: 40             # int; failures within window to open (20%)
    min_samples: 20                   # int; observations before the breaker can open
    open_duration: 5s                 # duration
    half_open_probes: 3               # int; consecutive successes required to close

  degraded:
    behaviour: open                   # enum: open | closed | degrade
    node_count_hint: 8                # int >= 1; fleet size used for derating

  global:                             # exactly one; no overrides permitted
    rate_per_sec: 5000                # int
    burst_multiplier: 1.2             # float; capacity = ceil(rate * multiplier)
    mode: enforce                     # enum: shadow | enforce

  defaults:
    route:
      rate_per_sec: 500
      burst_multiplier: 1.5
      cost: 1                         # int; tokens consumed per request (INV-5)
      mode: enforce

  tiers:
    anonymous:
      rate_per_sec: 5
      burst_multiplier: 2.0
      mode: enforce
    trial:
      rate_per_sec: 10
      burst_multiplier: 3.0
      mode: enforce
    standard:
      rate_per_sec: 100
      burst_multiplier: 2.0
      mode: enforce
    partner:
      rate_per_sec: 1000
      burst_multiplier: 2.0
      mode: enforce

  routes:
    documents.render:
      rate_per_sec: 200
      burst_multiplier: 1.25
      cost: 5                         # render is ~5x the cost of a plain read
      mode: enforce
    search.query:
      rate_per_sec: 400
      burst_multiplier: 1.5
      mode: enforce
    # any route not listed inherits defaults.route in full

  keys:
    # per-key overrides; fields are merged over the key's tier, field by field (D3)
    key_01J9ZC7QK4M2RB8VYX3TDN6H0P:
      tier: partner
      rate_per_sec: 2500              # override; burst_multiplier inherited (2.0)
      enabled: true
      note: "acme-corp; raised 2026-08-14 for Q3 migration; review 2026-11-01"
    key_01J8XA2FBQ7C5DKW1M9PZR4T6E:
      tier: trial
      enabled: false                  # explicit deny-all for this key (D3)
      note: "suspended for ToS violation 2026-08-02"
```

### Derived values

`capacity` is never written in config; it is always derived:

```
capacity = ceil(rate_per_sec * burst_multiplier)
```

For the shipped defaults:

| Definition | `rate_per_sec` | `burst_multiplier` | derived `capacity` |
|---|---|---|---|
| `global` | 5000 | 1.2 | 6000 |
| `defaults.route` | 500 | 1.5 | 750 |
| `routes.documents.render` | 200 | 1.25 | 250 |
| `routes.search.query` | 400 | 1.5 | 600 |
| `tiers.anonymous` | 5 | 2.0 | 10 |
| `tiers.trial` | 10 | 3.0 | 30 |
| `tiers.standard` | 100 | 2.0 | 200 |
| `tiers.partner` | 1000 | 2.0 | 2000 |
| `keys.key_01J9ZC7...` | 2500 | 2.0 (inherited) | 5000 |

### Go types — `internal/ratelimit/config.go`

```go
type Config struct {
    Enabled     bool              `yaml:"enabled"`
    ExemptPaths []string          `yaml:"exempt_paths"`
    Store       StoreConfig       `yaml:"store"`
    Redis       RedisConfig       `yaml:"redis"`
    Breaker     BreakerConfig     `yaml:"breaker"`
    Degraded    DegradedConfig    `yaml:"degraded"`
    Global      LimitConfig       `yaml:"global"`
    Defaults    DefaultsConfig    `yaml:"defaults"`
    Tiers       map[string]LimitConfig `yaml:"tiers"`
    Routes      map[string]LimitConfig `yaml:"routes"`
    Keys        map[string]KeyOverride `yaml:"keys"`
}

// LimitConfig fields are pointers so that "absent" is distinguishable from
// "explicitly zero" during per-field merge (D3).
type LimitConfig struct {
    RatePerSec      *int64   `yaml:"rate_per_sec"`
    BurstMultiplier *float64 `yaml:"burst_multiplier"`
    Cost            *int64   `yaml:"cost"`
    Mode            *Mode    `yaml:"mode"`
}

type KeyOverride struct {
    LimitConfig `yaml:",inline"`
    Tier    string `yaml:"tier"`
    Enabled *bool  `yaml:"enabled"`
    Note    string `yaml:"note"`
}

// StoreConfig, RedisConfig, BreakerConfig and DegradedConfig are plain structs whose
// fields map 1:1 onto the YAML keys above, with `time.Duration` for `sweep_interval`
// and `open_duration` and `int` for every count. StoreMode, Mode, Scope and
// DegradeBehaviour are string-backed enums with `UnmarshalYAML` validation.
```

`ResolvedLimit` is what `resolver.go` produces per scope, and is the only thing the
store ever sees:

```go
type ResolvedLimit struct {
    Scope             Scope  // ScopeKey | ScopeRoute | ScopeGlobal
    Identity          string // "key_01J...", "documents.render", "default"
    RatePerSec        int64
    Capacity          int64  // ceil(RatePerSec * BurstMultiplier)
    Cost              int64
    Mode              Mode
    RefillMilliPerSec int64  // RatePerSec * 1000
    CapacityMilli     int64  // Capacity * 1000
    CostMilli         int64  // Cost * 1000
    TTLSeconds        int64  // ceil(Capacity/RatePerSec) + IdleGraceSeconds
}
```

### Redis value encoding

Each bucket is a Redis hash with exactly two fields:

| Field | Type | Meaning |
|---|---|---|
| `t` | int64 | current token count in **millitokens** |
| `ts` | int64 | Unix epoch **milliseconds** of the last refill, from `redis.call('TIME')` |

Example: a `tiers.standard` key that has 87.4 tokens left, last touched at
`1787923200123`:

```
HGETALL rl:v1:key:{key_01J9ZC7QK4M2RB8VYX3TDN6H0P}
1) "t"
2) "87400"
3) "ts"
4) "1787923200123"
TTL  rl:v1:key:{key_01J9ZC7QK4M2RB8VYX3TDN6H0P}
(integer) 62
```

### Header reference

| Header | Present on | Value |
|---|---|---|
| `RateLimit-Limit` | all non-exempt | `rate_per_sec` of the attributed scope |
| `RateLimit-Remaining` | all non-exempt | `floor(tokens_milli / 1000)` of the attributed scope |
| `RateLimit-Reset` | all non-exempt | `ceil((capacity_milli - tokens_milli) / refill_milli_per_sec)` seconds |
| `RateLimit-Policy` | all non-exempt | `<rate>;w=1;burst=<capacity>` |
| `X-RateLimit-Scope` | all non-exempt | `key` \| `route` \| `global` |
| `X-RateLimit-Mode` | all non-exempt | `enforce` \| `shadow` \| `degraded` |
| `X-RateLimit-Shadow-Decision` | shadow mode only | `allow` \| `deny` |
| `Retry-After` | 429 only | `max(1, ceil(retry_after_ms / 1000))` seconds |

### Error codes

| HTTP | `error.code` | When |
|---|---|---|
| 429 | `rate_limit_exceeded` | Any scope denied in enforce mode |
| 429 | `api_key_suspended` | `keys.<id>.enabled: false` |

`api_key_suspended` carries `retry_after_ms: 0` and omits `Retry-After`, because
retrying will never succeed until an operator changes the config.

---

## Verification

### Phase A verification

**A-V1 — `bucket.go` unit tests** (`bucket_test.go`), table-driven, no clock:

- Refill from empty over exactly one full window reaches exactly `capacity_milli`.
  For `tiers.standard`: from `0` millitokens, `elapsed_ms = 2000`,
  `refill_milli_per_sec = 100000` → `0 + (2000 × 100000)/1000 = 200000` = capacity.
- Refill never exceeds capacity: same inputs with `elapsed_ms = 10000` → `200000`.
- `elapsed_ms < 0` (backwards clock) yields no change in token count.
- `Take` at exactly `tokens_milli == cost_milli` succeeds and leaves `0`.
- `Take` at `tokens_milli == cost_milli - 1` fails and leaves the count unchanged.
- `Refund` clamps at capacity (INV-4): `Refund(199500, 200000, 1000) == 200000`.
- `RetryAfterMilli(0, 1000, 100000) == 10` — 10ms to earn one token at 100/s.
- Property test (`testing/quick`, 10000 cases): for any sequence of `Take`/`Refill`
  operations, `0 <= tokens_milli <= capacity_milli` always holds.

**A-V2 — `MemoryStore` conformance suite** (`store_conformance_test.go`). This suite
is written once against the `Store` interface and is run against both backends; Phase
B reuses it verbatim. Cases:

- Fresh key: first `TakeBatch` sees a full bucket (D6).
- `capacity` consecutive takes of `cost=1` all succeed; take number `capacity+1` fails.
- After a denial, sleeping `RetryAfterMilli` and retrying succeeds.
- Expired key behaves as fresh: set `idle_grace_seconds: 0`, consume fully, advance
  the injected clock past TTL, verify the next take succeeds with a full bucket.
- `RefundBatch` restores exactly `cost_milli` and never exceeds capacity.
- Concurrency: 64 goroutines × 1000 takes of `cost=1` against a bucket of
  `capacity=200`, `rate=0` (no refill). Exactly `200` takes must succeed. Run under
  `-race`.

**A-V3 — `Limiter` scope-chain tests** (`limiter_test.go`), with a fake `Store`
that records the exact op sequence:

- Ops are submitted in the order `key`, `route`, `global` (INV-2).
- A scope with `rate_per_sec: 0` produces no op for that scope.
- Denial at `key` produces refund ops for `route` and `global`, and none for `key`.
- Denial at `route` produces refund ops for `key` and `global`, and none for `route`.
- Denial at `global` produces refund ops for `key` and `route`, and none for `global`.
- A scope that also denied in the same batch is never refunded (INV-3).
- A scope omitted from the chain (`rate_per_sec: 0`) is never refunded.
- Attribution on allow picks the lowest-fraction scope: given key at
  `180000/200000 = 0.90` and route at `300000/750000 = 0.40`, the attributed scope
  is `route`.
- Attribution tie at equal fractions resolves to `key` (D7).
- `keys.<id>.enabled: false` short-circuits with `api_key_suspended` and issues no
  store ops at all.

**A-V4 — `resolver.go` merge tests.** A key override that sets only
`rate_per_sec: 2500` against `tier: partner` resolves to
`{RatePerSec: 2500, BurstMultiplier: 2.0, Capacity: 5000, Cost: 1}`. An unknown
route resolves to `defaults.route` with identity `__unrouted__`.

**A-V5 — Header golden tests** (`headers_test.go`). Byte-exact assertions on the
full header set and JSON body for: an allow at 87 remaining tokens; a deny at the
`key` scope; a deny at the `global` scope; a shadow-mode deny; a suspended key.
`Retry-After` floor is asserted: `retry_after_ms: 40` must render `Retry-After: 1`,
not `0`.

**A-V6 — Middleware integration test** (`middleware_test.go`) against an
`httptest.Server` running the real chain: a request to `/healthz` is exempt and
carries no `RateLimit-*` headers; a request to an unknown path still consumes a
key-scope token (A6); denied requests appear in the access log.

**A-V7 — Latency benchmark.** `BenchmarkLimiterAllow_Memory` on the CI runner must
report **≤ 900 ns/op** and **0 allocations beyond 2 per op**. Enforced by
`benchstat` against a checked-in baseline in CI; a >10% regression fails the build.

**Phase A exit criteria:** conformance suite green under `-race`; benchmark within
budget; `ratelimit.enabled: false` produces byte-identical responses to the pre-change
build across the existing gateway integration suite.

### Phase B verification

**B-V1 — Conformance suite against `RedisStore`.** The A-V2 suite runs unmodified
against a real Redis 7.2 in a container (`testcontainers-go`). No mocks — the Lua
semantics are the thing under test.

**B-V2 — Lua script unit tests.** Directly `EVAL` `ratelimit_take.lua` and assert the
returned triple `{allowed, tokens, retry}`:

- Fresh key, `cap=200000`, `rate=100000`, `cost=1000` → `{1, 199000, 0}`.
- Bucket at `t=500`, `cost=1000`, `rate=100000` → `{0, 500, 6}` (6ms to earn 500
  more millitokens).
- `EXPIRE` is refreshed on every call: assert `TTL` returns the configured value
  after a second call 1s later.
- Absent key is treated as full (D6), asserted by `DEL` then `EVAL`.

**B-V3 — Distributed correctness.** Three gateway processes on one host, all pointed
at one Redis, all driving one key at `tiers.standard` (100 req/s, capacity 200).
Offer 600 req/s in aggregate for 60s. Assert total admitted requests fall in
`[5900, 6300]` — the nominal steady-state admission is `100 × 60 = 6000` plus the
initial 200-token burst, i.e. `6200`, and the band allows for the non-atomic
cross-scope window quantified in D4 (< 0.4%) plus timing jitter at the run boundaries.

**B-V4 — Breaker behaviour.** Using a Redis proxy (`toxiproxy`) between the gateway
and Redis:

- Inject 100% connection failures. Assert the breaker reaches `open` within 200
  operations, that `breaker_state` reports `2`, and that request latency drops back
  under 2ms (no timeout being paid).
- While open, assert the fleet still enforces: one pod, `standard` tier, derated to
  13 req/s / capacity 25. Offer 100 req/s for 10s; assert admitted count is in
  `[145, 165]` (nominal `13 × 10 + 25 = 155`).
- Restore Redis. Assert the breaker closes after `open_duration` plus 3 successful
  probes, and that `degraded_recovery_total` increments exactly once.
- Inject a 200ms latency toxic (above the 50ms timeout). Assert timeouts are
  classified as `backend_errors_total{kind="timeout"}` and drive the breaker.

**B-V5 — `behaviour: open` and `behaviour: closed`.** With Redis unreachable, assert
`open` admits 100% with `X-RateLimit-Mode: degraded` and no `RateLimit-*` numbers
claiming enforcement, and `closed` returns 429 `rate_limit_exceeded` with
`Retry-After: 1`.

**B-V6 — Shadow-mode divergence.** In `redis_shadow`, drive a key at 150 req/s
against a 100 req/s limit from two pods. Assert the memory store (authoritative)
admits everything below its per-pod limit, the Redis shadow decision denies, and
`shadow_divergence_total{authoritative="allow",shadow="deny"}` counts those. Assert
no request receives a 429.

**B-V7 — Redis load test.** Replay 30 minutes of production access-log traffic
(≈ 4200 req/s peak, ≈ 1900 distinct keys) through a staging gateway fleet of 8 pods
against a dedicated Redis 7.2 cluster of the same shape as production. Pass criteria:

- Added gateway p50 latency ≤ 1.5ms, p99 ≤ 6ms (the stated budget).
- Redis CPU on the busiest shard ≤ 35%.
- Zero `backend_errors_total`.
- Bucket key count plateaus rather than growing — evidence that TTLs are being set.

**B-V8 — Failover.** Trigger a Redis primary failover on one shard mid-load-test.
Assert the gateway sheds no more than 3 seconds of enforcement (breaker opens, then
closes), returns zero 5xx, and that `degraded_seconds_total` increases by ≤ 10.

**Phase B exit criteria:** B-V1 through B-V8 all green; the conformance suite passes
identically against both backends; load test within the latency budget.

### Phase C verification

**C-V1 — Config validation tests.** One test case per rule in C2, each asserting the
specific error message and that the previous config remains live. Explicitly included:
`burst_multiplier: 0.9` is rejected; `rate_per_sec: 0` is accepted and disables the
scope (not deny-all); an unknown `tier` name on a key is rejected; an unknown route id
in `routes` is rejected.

**C-V2 — Hot reload test.** Start with `tiers.standard.rate_per_sec: 100`, drive
steady traffic, rewrite the config file to `200`, and assert (a) no request errors
during the swap, (b) admitted rate rises to the new limit within 2 refill windows,
(c) `config_reload_total{outcome="applied"}` increments once. Then write an invalid
config and assert the limit stays at 200 and
`config_reload_total{outcome="rejected"}` increments.

**C-V3 — Rollback rehearsal (staging, manual, gated before stage 4).** Under load,
walk `redis` → `redis_shadow` → `memory` and back, one hot reload per step. Assert
zero 5xx and zero unintended 429s throughout, and record wall-clock time per step.
Target: each transition completes fleet-wide in under 30 seconds.

**C-V4 — Shadow-data review.** Before stage 4, produce a report from stage-3 data
listing, per key: observed p50/p99/max req/s, configured limit, and projected deny
rate under enforcement. Any key with a projected deny rate above 0.1% must have
either a documented override or a recorded notification before stage 4 proceeds
(C4).

**Phase C exit criteria:** C-V1/C-V2 green in CI; C-V3 rehearsed and timed; C-V4
report signed off by API Platform.

### Phase D verification

**D-V1 — Metric presence test.** A test that scrapes `/metrics` after driving one
allow, one deny, one shadow deny, one exempt request, and one forced backend error,
asserting every metric in the D1 table exists with the expected label set. This
catches label-name drift, which is the most common way a dashboard silently breaks.

**D-V2 — Cardinality guard.** A test asserting that no rate-limit metric carries a
`key_id`, `path`, or `identity` label. Implemented by scraping the registry after
driving 500 distinct synthetic keys and asserting the total rate-limit series count
stays under 400.

**D-V3 — Alert rule tests.** `promtool test rules` against a fixture time series for
each alert in D4: one firing case and one non-firing near-miss per rule. The
near-miss cases matter — e.g. `RateLimitDenyRateHigh` must not fire at 1.9% for 10m.

**D-V4 — Log assertion test.** Drive one deny and assert every field in D2 is present
with the correct type in the emitted JSON log line, and that an allowed request emits
none of them.

**D-V5 — Dashboard smoke.** After stage 3, confirm every panel on the
`gatewaysvc / rate limiting` dashboard renders non-empty data over a 24h window. An
empty panel means a query references a metric or label that does not exist.

**Phase D exit criteria:** D-V1 through D-V4 green in CI; D-V5 confirmed manually
before stage 4.

### Cross-cutting verification

**X-V1 — Backwards compatibility.** With `ratelimit.enabled: false`, the full existing
gateway integration suite passes with byte-identical responses to the pre-change
build, verified by a response-diffing harness over 5000 recorded requests.

**X-V2 — Security.** A test asserting that raw API key material never appears in any
Redis key, any metric label, any log field, or any response header. Implemented by
seeding a request with a sentinel secret value and grepping the captured Redis command
stream, metric dump, log output, and response headers for it.

**X-V3 — Chaos day.** After stage 5, a scheduled exercise: kill one Redis shard
primary, then partition the gateway from Redis entirely for 5 minutes, with SRE on
the dashboard. Success is (a) zero 5xx attributable to the limiter, (b) alerts fire
as specified in D4, (c) the on-call responder can state the current enforcement mode
from the dashboard alone within 60 seconds.

---

## Deferred

- **Adaptive limits** driven by backend health — control loop, oscillation risk;
  revisit after 3 months of steady-state data.
- **Concurrency limiting** per key (max in-flight) — different failure mode.
- **Long-window quotas** (daily/monthly) — owned by billing, PLAT-2290.
- **Cost weighting beyond a static `cost`** (e.g. by response size) — needs
  post-response accounting and a token-debt model.
- **Multi-policy `RateLimit-Policy`** as the IETF draft permits — deferred until
  integrator demand appears.
