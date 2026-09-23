# Pi LLM connectivity research

Research checkpoint: 2026-09-21. Scope is model access and transport only. This
is not yet a machine-specific configuration or a recommendation to put API keys
in this repository.

## Executive conclusion

Pi is a useful connection layer for this project because it can select among
subscription providers, direct API providers, OpenRouter, and local servers from
one CLI. The clean first design is three lanes:

1. **Local default:** the existing `llama.cpp` Docker server, preferably in
   router mode so Pi can load and unload GGUF models without changing the Pi
   session configuration.
2. **Hosted low-cost fallback:** OpenRouter pay-as-you-go with explicit model
   IDs and restricted provider routing, plus one direct provider for a stable
   baseline. OpenRouter is convenient but adds routing/data-policy complexity.
3. **Higher-capability escape hatch:** a subscription or direct API provider
   already available to the user, selected explicitly for tasks where local or
   budget models fail.

This separates harness experiments from provider lock-in. It also makes local
privacy the default and keeps external usage measurable.

Related durable documents: [provider and model landscape](pi-llm-provider-and-model-landscape-20260921.md),
[connectivity run](pi-connectivity-run-20260921.md), and the
[hosted-provider runbook](../artifacts/pi-hosted-provider-runbook.md).

## What Pi can connect to

Pi 0.86.1 is installed locally as `@earendil-works/pi-coding-agent`.
Its installed documentation and current pi.dev documentation describe:

| Lane | Connection mechanism | Main implication |
|---|---|---|
| Local `llama.cpp` | Built-in `llama.cpp` router integration; `/login llama.cpp`, `/llama`, `/model` | Best fit for the current Docker work; models are discovered/loaded by the router |
| Local OpenAI-compatible server | `~/.pi/agent/models.json` | Works with llama.cpp single-server mode, Ollama, LM Studio, vLLM, SGLang, and proxies |
| Direct APIs | Built-in provider catalogs plus env vars or `auth.json` | Less indirection and clearer billing/data terms |
| Aggregator | Built-in OpenRouter provider or custom OpenAI-compatible entry | Broad model choice and fallbacks; provider routing must be controlled deliberately |
| Subscription OAuth | `/login` for supported services | May avoid separate API keys, but entitlement and acceptable-use limits remain provider-specific |

Pi's supported custom API shapes are `openai-completions`,
`openai-responses`, `anthropic-messages`, and `google-generative-ai`. A provider
can therefore be added without an extension when it faithfully implements one
of those protocols; custom OAuth or a non-compatible protocol requires an
extension.

The installed 0.86.1 docs are not a timeless provider catalogue. Current pi.dev
documentation lists additional providers and subscription paths that may not be
present in an older binary. Before using a provider in a durable runbook, check
both `pi --version` and `pi --list-models` (with network refresh enabled).

## Local llama.cpp path

Pi has a dedicated router integration. The documented server shape is:

```bash
llama-server \
  --models-dir ~/models \
  --no-models-autoload \
  --jinja \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl 999 \
  -c 32768
```

Then use `/login llama.cpp`, or:

```bash
export LLAMA_BASE_URL=http://127.0.0.1:8080
export LLAMA_API_KEY=optional-secret
```

Important constraints:

- Start `llama-server` without `--model`, `-m`, or `-hf`; those select
  single-model mode instead of router mode.
- `--jinja` matters for modern chat templates and tool calling.
- Only loaded models appear in Pi's `/model`; `/llama` performs load/unload and
  can download GGUFs from Hugging Face.
- Keep the server bound to `127.0.0.1` unless remote access is intentional.
- If using a generic OpenAI-compatible entry in `models.json`, expect to set
  `supportsDeveloperRole: false` and `supportsReasoningEffort: false` for
  servers that do not implement those request features.

The current Docker server should first be tested against Pi's router protocol,
not assumed compatible merely because `/v1/chat/completions` works. Verify
`/health`, `/models`, model load/unload, streaming, tool calls, and context
limits.

## Hosted options worth testing

These are connection candidates, not claims that every current model is equally
good for coding-agent work. Model IDs, pricing, rate limits, and availability
must be refreshed before each benchmark.

| Provider/path | Why it belongs in the test set | Watch-outs |
|---|---|---|
| OpenRouter | One API for a large, changing catalogue; Pi supports API keys and OAuth-minted keys | Standard pay-as-you-go currently carries a platform fee; free access has a small model/provider set and a 50-request/day limit; fallback routing can change the upstream provider |
| Google Gemini API | A free tier exists for selected models; paid tier has higher limits and Google states paid content is not used to improve products | Free-tier content-use terms differ; tool-calling and coding quality vary by model; verify current model IDs and regional availability |
| DeepSeek direct | Usually a strong low-cost reasoning/coding baseline and OpenAI-format endpoint | Provider-specific retention/training terms need reading; current model/pricing page is volatile; do not infer privacy from OpenAI compatibility |
| Groq / Cerebras | Very fast hosted inference for open models; useful for short edits, classification, and rapid feedback | Throughput/rate limits and model availability are the product; latency is not the same as agent quality |
| Mistral direct | European provider and direct API path; sensible open-model and coding candidates | Current model catalogue, tool support, and retention guarantees vary by plan/API |
| Together / Fireworks | Broad open-model hosting with more control than an aggregator; useful for comparing Qwen, DeepSeek, Llama, and similar families | Per-token prices, throughput tiers, and data policies vary by endpoint; verify tool-calling support per model |
| Cloudflare Workers AI / AI Gateway | Useful if Cloudflare is already part of the deployment boundary; gateway can unify upstreams, BYOK, and observability | Adds another control plane; distinguish Workers AI models, unified billing, stored BYOK, and inline BYOK |
| OpenCode Zen/Go, Z.ai, Kimi, Qwen token plans, MiniMax | Pi has provider entries for several coding-focused services and plans | Treat plan quotas and acceptable-use limits as subscription products, not unlimited API capacity |

For the first inexpensive hosted benchmark, use one direct path (Gemini or
DeepSeek), one fast open-model path (Groq or Cerebras), and OpenRouter with
provider pinning. This gives useful comparison without wiring every provider at
once.

## OpenRouter-specific design

OpenRouter is best treated as a catalogue/router, not as a privacy boundary.
Its API exposes model/provider metadata and pricing, and its routing can choose
among upstream providers. For reproducible experiments:

- pin an exact model ID rather than a broad alias;
- restrict or explicitly order upstream providers when data location or policy
  matters;
- record the returned model/provider, latency, input/output tokens, and errors;
- use provider data-policy filters where the account tier supports them;
- do not send secrets or proprietary source to free/fallback routes until the
  selected upstream policy is confirmed.

OpenRouter's current pricing page says the free tier has 25+ free models, four
free providers, and 50 requests/day; Standard pay-as-you-go lists a 5.5%
platform fee and provider-passthrough rate limits. These values are dated
observations, not durable configuration constants.

## First-wave shortlist

The research agents' practical recommendation is:

- **Local:** current `llama.cpp` router as the privacy-preserving baseline.
- **Primary hosted budget lane:** direct paid Gemini Flash, with a billing cap.
  Google distinguishes free-tier data use from paid API data-use terms, so do
  not treat the free tier as the privacy-equivalent option.
- **Open-model bulk lane:** Together first; benchmark its current cheap
  function-calling models on non-sensitive tasks. Fireworks is a comparable
  alternative when serverless throughput or future dedicated deployment matters.
- **EU/privacy-sensitive hosted lane:** direct Mistral, but only after the
  applicable endpoint and ZDR eligibility are confirmed. EU processing alone is
  not a retention guarantee.
- **Fast short-loop lane:** Groq or Cerebras for triage and small edits. Their
  speed is useful, but it does not make them the default for difficult
  repository-level reasoning.
- **Evaluation/fallback lane:** OpenRouter with an exact model and explicit
  provider allowlist. Broad automatic fallback is inappropriate for sensitive
  code because the upstream processor can change.
- **Non-sensitive experiment only:** DeepSeek direct until its current retention
  and training terms are acceptable for the material being sent.

These are routing roles, not permanent model rankings. Token prices, model IDs,
free quotas, context windows, and rate limits are volatile and should be
captured by the benchmark at run time.

## Minimal connection test plan

Run the same small repository task through each lane:

1. `pi --provider llama.cpp --model <loaded-model>`: read-only repository map.
2. A tool-calling task that edits one disposable file, then checks the diff.
3. A longer-context task with an intentionally bounded context window.
4. The same prompts through one direct hosted API and OpenRouter.
5. Record success, tool-call validity, time-to-first-token, total latency,
   input/output tokens, estimated cost, and whether the model needed human
   correction.

Do not rank models by chat quality alone. For this use case, valid tool calls,
stable multi-turn state, context handling, and predictable failure behavior are
more important than a single benchmark score.

## Sources and evidence

- Pi providers: https://pi.dev/docs/latest/providers
- Pi custom models and compatibility: https://pi.dev/docs/latest/models
- Pi llama.cpp integration: installed `pi/docs/llama-cpp.md` and
  https://pi.dev/docs/latest/providers#llamacpp
- llama.cpp OpenAI-compatible server: https://github.com/ggml-org/llama.cpp
- OpenRouter pricing and limits: https://openrouter.ai/pricing
- OpenRouter provider metadata/routing API:
  https://openrouter.ai/docs/api/api-reference/providers/list-all-providers
- Gemini API pricing and data-use tiers:
  https://ai.google.dev/gemini-api/docs/pricing
- DeepSeek models/pricing: https://api-docs.deepseek.com/quick_start/pricing/
- Fireworks pricing: https://fireworks.ai/pricing

## Deferred

Configuration files, secret-management integration, benchmark harness code,
Pi extensions/skills, and a final model shortlist should follow a successful
connectivity smoke test. They should not be mixed into this research checkpoint.
