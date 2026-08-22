# Answer Key — synthetic-target.md (gatewaysvc rate limiting plan)

Blind judging key for the defect-injected target document. 13 injected defects total.
Match a reviewer's finding to an entry by mechanism/section/value, not by wording.

## Summary

**Total defects: 13**

| Category | Count |
|---|---|
| Showstopper | 1 |
| Inconsistency | 5 |
| Gap | 4 |
| Underspecified | 3 |

| Difficulty | Count |
|---|---|
| surface-contradiction | 4 |
| arithmetic-derivation | 2 |
| cross-section | 7 |

| # | Category | Difficulty | Location |
|---|---|---|---|
| 1 | Showstopper | surface-contradiction | D5 degraded-mode default vs config schema `degraded.behaviour` |
| 2 | Inconsistency | surface-contradiction | Constraints latency budget vs B-V7 / D4 "stated budget" |
| 3 | Inconsistency | surface-contradiction | D3 scope precedence — evaluation-order prose vs INV-2 |
| 4 | Inconsistency | surface-contradiction | Goals fleet size vs Constraints replica count |
| 5 | Inconsistency | arithmetic-derivation | D6 TTL worked-values table, `defaults.route` row |
| 6 | Inconsistency | arithmetic-derivation | B-V2 Lua script unit test, retry-ms result |
| 7 | Gap | cross-section | Hot-reload of `store.mode` (D2/C1) vs Limiter/Store call-shape wiring (A5 vs B5) |
| 8 | Gap | cross-section | Shadow evaluation (B5) error/timeout reporting |
| 9 | Gap | cross-section | `decisions_total` outcome enum (D1) vs shadow semantics (B5) |
| 10 | Underspecified | cross-section | Config resolution `tier_of_key` (D3) vs `KeyOverride` type |
| 11 | Underspecified | cross-section | Partner override expiry (C4) vs validation rules (C2) |
| 12 | Underspecified | cross-section | A5 Cost resolution (`Limiter.Allow` step 2) vs `LimitConfig.Cost` on Keys/Tiers/Global (Schema) |
| 13 | Gap | cross-section | Error codes table vs `closed` degraded mode (D5) vs alert rationale (D4) |

---

## 1. Showstopper — degraded-mode default contradicts its own design rationale

**Category:** Showstopper
**Difficulty:** surface-contradiction
**Location:** D5 ("Behaviour under backend failure: degrade, not fail-open") vs the `ratelimit.degraded` block in the config schema.

D5 states plainly: "Three configurable behaviours, with `degrade` as the default," and spends a paragraph explaining why `open` is unacceptable as a default ("the common industry default but leaves us with no protection during exactly the kind of event... the INC-4412 condition"). The shipped config schema's `degraded` block sets `behaviour: open`. If deployed as documented, a Redis outage admits all traffic unthrottled — precisely the INC-4412 scenario the whole project exists to prevent — despite the design section explicitly rejecting that as the default. This isn't a cosmetic mismatch: it silently defeats the primary goal of the plan (graceful degradation) under the exact failure condition it was built to survive.

## 2. Inconsistency — latency budget stated two different ways

**Category:** Inconsistency
**Difficulty:** surface-contradiction
**Location:** Constraints (top of doc) vs Phase B verification B-V7 and D4's rationale for rejecting sequential Redis round trips.

Constraints states the added-latency budget as "p99 ≤ 8 ms." Both B-V7's pass criteria ("Added gateway p50 latency ≤ 1.5ms, p99 ≤ 6ms (the stated budget)") and D4's batching rationale ("Three sequential RTTs at p99 2.1ms would consume 6.3ms and blow the 6ms p99 budget") explicitly reference a 6ms budget. Two different numeric ceilings are asserted for the same constraint, and the D4 rationale for choosing pipelining over sequential calls only holds under the 6ms figure — under the Constraints section's stated 8ms, sequential RTTs (6.3ms) would actually fit, undermining the stated justification for D4's design choice.

## 3. Inconsistency — scope evaluation order reversed within the same section

**Category:** Inconsistency
**Difficulty:** surface-contradiction
**Location:** D3 ("Scope precedence and enforcement") — the "Evaluation order" paragraph vs INV-2, a few lines below it in the same subsection.

The prose states: "Evaluation order: `route` → `key` → `global` (most specific first)." INV-2, listed immediately after, states: "Scopes are evaluated most-specific first: `key`, then `route`, then `global`." These are direct, adjacent, incompatible statements of the same fact (which scope is evaluated first) inside one design section. This also has downstream implications the doc treats as settled elsewhere (D4's claim that evaluation order is preserved through the pipeline "for attribution and refunds," and D7's/A-V3's assumption that ops are submitted `key, route, global`), so a reviewer who only reads D3 would already catch it without cross-referencing.

## 4. Inconsistency — fleet size stated two different ways

**Category:** Inconsistency
**Difficulty:** surface-contradiction
**Location:** Goals (item 3) vs Constraints, two adjacent sections near the top of the document.

Goal 3 states the system must "Work across the fleet (**8** pods per region, 3 regions), not just per-process." The Constraints section immediately below states "gatewaysvc is... a Kubernetes Deployment, **6** replicas per region." Every later use of the fleet size (D2's per-pod throttling example "8 pods... 100 req/s could sustain up to 800 req/s... or be throttled to 12.5 req/s"; D5's derating math `ceil(100/8)=13`; the config schema's `degraded.node_count_hint: 8`) consistently uses 8, making the Constraints line the outlier — a reviewer has to notice one line contradicts both the adjacent Goals statement and the load-bearing "8" used throughout the rest of the design.

## 5. Inconsistency — TTL table entry doesn't match its own formula

**Category:** Inconsistency
**Difficulty:** arithmetic-derivation
**Location:** D6 ("Missing bucket means full bucket"), the worked-TTL-values table, `defaults.route` row.

The TTL formula given just above the table is `ttl_seconds = ceil(capacity / refill_rate_per_sec) + idle_grace_seconds`, with `idle_grace_seconds` defaulting to 60. For `defaults.route` (`rate_per_sec: 500`, `capacity: 750`), `ceil(750/500) = ceil(1.5) = 2`, so TTL should be `2 + 60 = 62`. The table's `ceil(cap/rate)` column correctly shows `2`, but the TTL column shows `61s` instead of `62s` — an off-by-one that only surfaces if the reader actually applies the stated formula to the row's own inputs rather than trusting the printed value.

## 6. Inconsistency — Lua script test result doesn't match the algorithm it's testing

**Category:** Inconsistency
**Difficulty:** arithmetic-derivation
**Location:** Phase B verification, B-V2 ("Lua script unit tests"), second bullet.

The bullet asserts: bucket at `t=500` (500 millitokens), `cost=1000`, `rate=100000` (millitokens/sec) → result `{0, 500, 6}`, i.e. "6ms to earn 500 more millitokens." Applying the retry formula given in `ratelimit_take.lua` itself (`retry = ceil(((cost - toks) * 1000) / rate)`): `ceil((1000 - 500) * 1000 / 100000) = ceil(5) = 5`, not 6. The stated test fixture is wrong relative to the algorithm it's meant to be verifying — a reviewer has to actually run the formula on the given inputs to catch it, since the surrounding prose ("6ms to earn 500 more millitokens") is internally consistent with the (wrong) "6".

## 7. Gap — hot-reloading `store.mode` has no described mechanism for switching the Limiter's actual call shape

**Category:** Gap
**Difficulty:** cross-section
**Location:** D2 ("Storage backend") / C1 ("Config loading and hot reload") vs A5 (`Limiter.Allow` algorithm) vs B5 ("Shadow evaluation").

D2 and C1 both state that `ratelimit.store.mode` is a plain hot-reloadable config key: "The mode is one hot-reloadable config key... Rolling back from `redis` to `memory` needs no restart and no data migration" (D2), and C1's reload mechanism is described purely as swapping a `*Config` via `atomic.Pointer[Config]`. But the three modes require structurally different call shapes from the `Limiter`, not just different parameter values: A5's core algorithm issues one `store.TakeBatch(ctx, ops)` call against a single `Store`, whereas B5 states that in `redis_shadow` mode "`Limiter.Allow` calls the memory store (authoritative) and the Redis store (observational) concurrently" — two separate stores, called differently, with a `100ms` budget on only one of them. Nothing in the document describes how a live `Limiter`/`Store` object graph — constructed once, per A1/B4 — restructures itself between these two call shapes (or reconstructs which physical `Store` instance(s) it holds, e.g. plugging in `RedisStore` when moving off `memory`) when `store.mode` changes at runtime. The claim that this transition "needs no restart" is never reconciled with the fact that the two modes are architecturally different data flows, not just different config values read by the same code path.

## 8. Gap — shadow-path failure has no defined reporting

**Category:** Gap
**Difficulty:** cross-section
**Location:** Phase B, B5 ("Shadow evaluation") vs D7 (headers) and the metrics table (D1).

B5 states the shadow (Redis) call in `redis_shadow` mode "never lets the shadow path fail the request" but never specifies what is reported when the shadow call itself errors or times out (as opposed to completing with an allow/deny). Neither the `X-RateLimit-Shadow-Decision` header (D7, which only documents `allow`/`deny` values) nor the metrics table (D1, whose `shadow_divergence_total` counter is keyed by `authoritative`/`shadow` outcome labels, not error states) has a slot for "shadow evaluation failed" — so an operator watching shadow-mode data during the Phase C rollout has no way to distinguish "Redis agreed/disagreed" from "we don't know because the shadow call errored," which directly undermines the stated purpose of shadow mode (validating Redis correctness before cutover).

## 9. Gap — `decisions_total` outcome taxonomy is incomplete for shadow mode

**Category:** Gap
**Difficulty:** cross-section
**Location:** Phase D, D1 metrics table (`decisions_total` labels) vs Phase B, B5 (shadow evaluation semantics).

The `decisions_total` counter's `outcome` label enum is given as `allow`\|`deny`\|`shadow_deny`\|`exempt`. There is no `shadow_allow`. Per B5, in `redis_shadow` mode every request produces both an authoritative (memory) decision and a shadow (Redis) decision, and the shadow decision can be either allow or deny — only the deny case has a home in `decisions_total`. A request where the shadow decision is "allow" is invisible in this counter, and is otherwise only surfaced via `shadow_divergence_total`, which only increments on divergence — so a shadow-allow that agrees with the authoritative decision (the common case) leaves no trace anywhere in the metrics for how many requests shadow mode is actually evaluating.

## 10. Underspecified — tier resolution for a key with no config entry

**Category:** Underspecified
**Difficulty:** cross-section
**Location:** D3 ("Configuration resolution (specificity)") vs the `KeyOverride` Go type in the Schema section.

D3's resolution chain is given as `keys.<key_id> → tiers.<tier_of_key> → tiers.standard`, which requires knowing `tier_of_key` before the second step can even be attempted. But `tier_of_key` (the `Tier` field) only exists on a `KeyOverride` record — i.e. only for keys that already have a `keys.<id>` entry in config. For an authenticated key with no entry in `keys` at all (the common case — most keys presumably aren't individually configured), the doc never states what tier it resolves to. `tiers.standard` is named as the final fallback in the chain, but the chain as written can't reach that fallback without a `tier_of_key` that doesn't exist for such a key — it's unclear whether an unlisted key should be treated as tier `standard` directly, or whether this is a hole in the resolution algorithm as specified.

## 11. Underspecified — temporary partner overrides have no expiry enforcement

**Category:** Underspecified
**Difficulty:** cross-section
**Location:** C4 ("Partner communication") vs C2 ("Validation rules").

C4 describes granting a temporary `keys.<id>` override to a partner whose observed rate exceeds their tier limit, "with an expiry date recorded in the config comment." A YAML comment is not machine-readable config. C2's validation rules (the exhaustive list of what's checked at config load) never reference this expiry date, and no other section describes any automation, alert, or process that reverts or flags an override past its recorded expiry. As written, the "expiry" is purely documentary — nothing in the system prevents a temporary rate bump from becoming a permanent, unreviewed one.

## 12. Underspecified — the `Cost` field on Keys/Tiers/Global scopes is never read by the resolution algorithm

**Category:** Underspecified
**Difficulty:** cross-section
**Location:** A5 (`Limiter.Allow` algorithm, step 2) vs `LimitConfig.Cost` in the Go types (Schema, ~lines 894-899) vs D3's general per-field resolution mechanism.

`LimitConfig` — the struct backing `Global`, every entry in `Tiers`, every entry in `Routes`, and (via the embedded `KeyOverride`) every entry in `Keys` — carries a `Cost *int64` field, structurally available on all four scopes. D3 describes configuration resolution as a generic per-field walk from most specific to least specific ("Resolution is per field, not per block... Operators never have to restate a full block to change one number"), which reads as applying to every field `LimitConfig` exposes, `Cost` included. But A5's algorithm states plainly that `CostMilli` "is resolved once, from the matched route's `cost`... and copied onto every `Op` in the chain — the `Cost` field on `keys.<id>`, `tiers.<tier>`, and `global` is not consulted by this step." So the field is real, settable in YAML, and silently inert everywhere except `routes`/`defaults.route` — an operator who sets `tiers.partner.cost` or a per-key `cost` override (both syntactically valid per the schema) gets no error and no effect. Nothing in the doc flags this scope restriction outside that one clause in A5, and it sits in tension with D3's general per-field promise and with INV-5's framing of `cost` as a property "each scope" consumes independently.

## 13. Gap — no error code distinguishes an outage-driven 429 from a real rate-limit deny

**Category:** Gap
**Difficulty:** cross-section
**Location:** Error codes table (Schema section) vs D5's `closed` degraded-mode behaviour vs D4's rationale for `RateLimitDenyRateHigh`.

The Error codes table defines exactly two `error.code` values: `rate_limit_exceeded` and `api_key_suspended`. D5 defines a `closed` degraded-mode behaviour ("Deny everything with 429") for when the Redis store is unavailable, but nothing in the doc gives that case a distinct `error.code` — it would presumably also be reported as `rate_limit_exceeded`, indistinguishable from a genuine per-key/route/global limit denial. This matters because D4 explicitly justifies `RateLimitDenyRateHigh` being a ticket rather than a page on the grounds that "a high deny rate during an actual abuse event is the system working correctly" — a rationale that does not hold if the actual cause is backend unavailability (`closed` mode) rather than a caller exceeding their limit, and the alert has no way to distinguish the two cases given the shared error code.
