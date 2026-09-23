# Pi LLM provider and model landscape

**Research date:** 21 September 2026  
**Scope:** models and providers that can be used from Pi, with emphasis on
lower-cost alternatives to Anthropic/OpenAI API billing. The user already has
Anthropic and OpenAI subscriptions, so those APIs are treated as subscription
fallbacks rather than recommended metered providers.

## Executive summary

For the current phase, the most useful Pi setup is a hosted-provider portfolio,
not one universal model:

1. **Hosted comparison layer:** use OpenRouter with hard ZDR routing, provider
   allowlists, and pinned model IDs. This gives the fastest way to compare
   models without silently falling back to a non-compliant provider.
2. **First-tier cheap models:** test Qwen3.8-Flash, DeepSeek `deepseek-flash`
   (V4.1-Flash), and GLM-5.3-Flash. Their current coding/agent evidence is
   strong enough that they should not be treated as merely bulk workers.
3. **ZDR-oriented direct alternatives:** use Groq GPT-OSS, Fireworks open-model
   endpoints where the exact ZDR terms are confirmed, or Mistral Small 4 if
   paid-plan ZDR and European processing are important.
4. **Fast short-loop provider:** use Groq GPT-OSS 20B/120B when latency matters
   more than maximum reasoning quality.
5. **Capability baseline:** keep Gemini 3.8 Flash for difficult tasks and as a
   comparison point, but not as the low-cost default.
6. **Alternative gateway:** use Vercel AI Gateway or Hugging Face Inference
   Providers when a single catalogue and provider-selection layer is useful.
   Cloudflare AI Gateway is primarily a control plane and BYOK proxy, not
   automatically a cheaper model marketplace.

The cheapest model is not necessarily the cheapest coding-agent option. A model
that makes malformed tool calls, loses state, or needs repeated correction can
consume more tokens and time than a moderately more expensive reliable model.

All prices, model IDs, quotas, and provider availability below are dated
observations. Recheck the provider catalogue before spending money or putting a
model in a durable runbook.

## How Pi connects to providers

Pi 0.86.1 is installed locally as `@earendil-works/pi-coding-agent`. Pi supports:

- built-in provider catalogues and API-key authentication;
- OAuth/subscription logins for selected services;
- custom providers and models in `~/.pi/agent/models.json`;
- `openai-completions`, `openai-responses`, `anthropic-messages`, and
  `google-generative-ai` transports;
- first-class `llama.cpp` router integration.

Typical built-in use is:

```bash
export GEMINI_API_KEY=...
pi --provider google --model gemini-3.8-flash
```

For a custom OpenAI-compatible endpoint:

```json
{
  "providers": {
    "local": {
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "local",
      "models": [
        {
          "id": "model-id",
          "reasoning": true,
          "contextWindow": 32768,
          "cost": { "input": 0, "output": 0 }
        }
      ]
    }
  }
}
```

Partial OpenAI-compatible servers may require:

```json
"compat": {
  "supportsDeveloperRole": false,
  "supportsReasoningEffort": false,
  "supportsUsageInStreaming": false
}
```

The model must support Pi's actual agent loop: function schemas, streaming
tool calls, tool-result replay, and multi-turn context. Text-generation quality
alone is insufficient.

Sources: [Pi providers](https://pi.dev/docs/latest/providers), [Pi custom
models](https://pi.dev/docs/latest/models), [Pi SDK/model registry](https://pi.dev/docs/latest/sdk).

## Local models through llama.cpp

Pi's dedicated router workflow is the best fit for the current Docker work:

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

Then authenticate the connection with `/login llama.cpp`, use `/llama` to load
or unload a GGUF, and use `/model` to select the loaded model. Start without
`--model`, `-m`, or `-hf`; those select single-model mode rather than router
mode. `--jinja` is important for modern chat templates and tool calling.

### Local shortlist

| Model | Approximate Q4 weight size | Practical hardware | Pi suitability |
|---|---:|---:|---|
| Qwen3.5 9B | about 5–6 GB | 16 GB RAM/unified memory | Small local default; tool use and optional thinking, but keep tasks bounded |
| Devstral Small 2 24B | about 14 GB | 24 GB VRAM or 32 GB unified memory | Best first local agentic-coding candidate; native tool format |
| Qwen3-Coder 30B-A3B Instruct | about 18–19 GB | 24 GB VRAM at modest context; 32–48 GB safer | Coding-specialised MoE with native tool support; non-thinking model |
| Qwen3.8 27B | about 16–18 GB | 24 GB VRAM or 32 GB unified memory | Strong local Qwen3.8 candidate if the hardware can sustain it; compare against Devstral on real Pi tasks |
| GLM-4.7-Flash 30B-A3B | about 18 GB | 24–48 GB memory | Reasoning/tool-use alternative; validate the exact chat template |
| Larger 70B–120B open models | commonly 40–80+ GB Q4 | 64 GB+ memory and/or multiple GPUs | Potentially stronger, but poor first target for a single consumer machine |

Q4 file size is only a lower bound. Runtime buffers and KV cache consume
additional memory, and long context can dominate the total. Begin at 16–32K
context even when the model card advertises 128K–256K. Official GGUF and
llama.cpp guidance is available for [Devstral Small 2](https://huggingface.co/ggml-org/Devstral-Small-2-24B-Instruct-2512-GGUF),
[Qwen3-Coder](https://huggingface.co/Qwen/Qwen3-Coder-Next-GGUF), and
[llama.cpp](https://github.com/ggml-org/llama.cpp).

Local cost is approximately zero per token. It is better understood as fixed
hardware/electricity cost plus latency and maintenance. It is also the clearest
data boundary: prompts, repository contents, and tool results remain local if
the model server and telemetry are configured locally.

## Hosted model comparison

Prices are USD per million tokens, standard input/output, unless stated
otherwise. Caching, batch, priority tiers, taxes, and gateway fees can change
the effective price.

| Provider and model | Input | Output | Capability/use | Main caveat |
|---|---:|---:|---|---|
| Groq `openai/gpt-oss-20b` | $0.075 | $0.30 | Very fast lightweight reasoning/tool loops | Free/developer limits; not the strongest long-horizon coder |
| DeepSeek `deepseek-flash` (V4.1-Flash) | $0.15 off-peak / $0.30 peak | $0.60 off-peak / $1.20 peak | First-tier coding and agent candidate; 1M context, tool calls, Responses API, and vision | Direct provider policy/jurisdiction is a serious privacy constraint; output price is higher than the old V4 Flash table |
| Together `GLM-5.3-Flash` | $0.15 | $0.50 | Cheap general coding and tool-call candidate | Validate current function-call behavior in Pi |
| Alibaba Cloud `qwen3.8-flash` | $0.15 | verify live catalogue | First-tier coding/agent candidate; 1M context, multimodal input, OpenAI/Anthropic-compatible APIs | Verify current output price, region, quotas, and exact endpoint |
| Groq `openai/gpt-oss-120b` | $0.15 | $0.60 | Larger open-weight reasoning fallback | Developer tier currently lists 250K TPM and 1K RPM |
| Mistral Small | about $0.15 | about $0.60 | Direct European-provider option; good cost-sensitive path | Verify exact current model ID, endpoint, and ZDR eligibility |
| Gemini 3.8 Flash | $0.75 | $3.75 | Best first serious hosted baseline; long-horizon coding and tool use | Introductory pricing ends 31 December 2026 |
| Vercel `alibaba/qwen3-coder-next` | $0.50 | $1.20 | Hosted coding model through a managed gateway | Routing/provider selection must be pinned |
| Together `gpt-oss-120B` | $0.15 | $0.60 | Open-weight reasoning through a direct host | Tool reliability is provider/model-specific |
| Fireworks open models | model-dependent | model-dependent | Broad catalogue, serverless-to-dedicated migration path | Current per-model prices must be fetched from its live catalogue |
| Cerebras open models | model-dependent | model-dependent | Very low latency | Direct pricing/model availability needs account-level verification |

Together's current serverless table gives the clearest low-cost catalogue:
GLM-5.3-Flash at $0.15/$0.50, GPT-OSS 120B at $0.15/$0.60, and Qwen3.5 9B
at $0.17/$0.25. [Together pricing](https://www.together.ai/pricing)

Qwen3.8-Flash deserves first-tier testing rather than being treated as a
routine-only model: Alibaba describes it as multimodal, 1M-context, and
compatible with both OpenAI and Anthropic API protocols, and reduced its input
price to $0.15 per million tokens. Verify the current output price in the live
catalogue. [Qwen3.8-Flash price notice](https://www.alibabacloud.com/en/notice/model_studioqwen38flash_price_reduction_notice_859)

The DeepSeek model name also needs care. The current direct API model is
`deepseek-flash`, which serves DeepSeek-V4.1-Flash; legacy V4 Flash names are
temporarily routed to it. It supports tool calls, the Responses API, vision,
and 1M context. Official pricing is peak/off-peak: $0.30/$1.20 or
$0.15/$0.60 per million input/output tokens, respectively. The provider also
reports strong agent benchmarks, but those results should still be validated
in Pi because benchmark harness and reasoning-effort settings materially affect
agent outcomes. [DeepSeek V4.1-Flash release](https://api-docs.deepseek.com/news/news260910/),
[DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/)

Groq publishes current model prices and rate limits. Its GPT-OSS 20B and 120B
entries are $0.075/$0.30 and $0.15/$0.60 respectively, with 131K context
windows and developer-tier limits shown in the catalogue. [Groq models](https://console.groq.com/docs/models),
[Groq limits](https://console.groq.com/docs/rate-limits)

Gemini 3.8 Flash is currently $0.75/$3.75 through 31 December 2026, with
standard prices of $1.50/$7.50 from 1 January 2027. Google specifically
describes longer-running tool use and iterative verification for this model.
[Gemini model announcement](https://ai.google.dev/gemini-api/docs/latest-model)

Mistral's pricing page gives Mistral Large as an example at $0.50/$1.50 and
states that batch can halve price and cached input can reduce input cost by up
to 90%. Cost-sensitive projects are directed toward Mistral Small; verify its
current exact price before budgeting. [Mistral pricing](https://mistral.ai/pricing/)

### Hosted-first model and provider shortlist

The model and the serving endpoint must be evaluated separately. The same
Qwen, DeepSeek, or GPT-OSS weights can have different prices, tool behaviour,
regions, and retention terms depending on whether they are served by the model
owner, Together, Fireworks, Groq, OpenRouter, or another gateway.

| Model | Providers to try | Current cost signal | Why it belongs in the first test | Main qualification |
|---|---|---:|---|---|
| **Qwen3.8-Flash** | OpenRouter with ZDR; Together; Alibaba Model Studio | Together $0.15/$0.47; Alibaba input price $0.15, verify output live | Strong quality-per-dollar candidate with 1M context, multimodal input, reasoning controls, and tool/API compatibility | Confirm endpoint-specific retention and actual output price |
| **DeepSeek V4.1-Flash** (`deepseek-flash`) | OpenRouter with ZDR; Fireworks/Together if endpoint policy qualifies; direct DeepSeek for non-sensitive work | Official $0.15/$0.60 off-peak; $0.30/$1.20 peak | Strongest current vendor-reported agent results in this set; 1M context, tool calls, Responses API, vision | Direct DeepSeek is not a ZDR recommendation; benchmark results use DeepSeek’s own harness and max effort |
| **GLM-5.3-Flash** | OpenRouter with ZDR; Together | Together $0.15/$0.50 | Strong independent small-sample hosted comparison and good cost/latency balance | Validate provider’s exact tool-call and retention behaviour |
| **GPT-OSS 120B** | Groq; Together; OpenRouter with ZDR | $0.15/$0.60 | Useful open-model control; Groq adds very low latency and explicit data controls | Tool reliability may trail Qwen/GLM/DeepSeek on difficult loops |
| **GPT-OSS 20B** | Groq; OpenRouter with ZDR | Groq $0.075/$0.30 | Cheapest serious fast worker for triage, routing, review, and retries | Not the first choice for autonomous multi-file work |
| **Mistral Small 4** | Direct Mistral paid ZDR endpoint; OpenRouter if pinned to a qualifying provider | $0.15/$0.60 | Best explicit European ZDR-oriented alternative in this price band | Mistral ZDR is limited to eligible paid, stateless endpoints; do not use stateful Agents/Files APIs for this privacy requirement |
| **Gemini 3.8 Flash** | Direct Google; OpenRouter if policy route is acceptable | $0.75/$3.75 introductory | More expensive capability/reliability baseline for long-horizon tasks | Not the low-cost default and account/product data terms must be checked |

An independent 19-prompt Flash-tier comparison reported GLM-5.3-Flash with the
highest average score, followed by DeepSeek V4.1-Flash and Qwen3.8-Flash;
Qwen had the lowest recorded cost. This is a small directional test, not a
replacement for a Pi-specific coding benchmark. Vendor-reported DeepSeek and
Qwen scores should likewise be treated as evidence for testing, not proof of
ranking in Pi. [Flash-tier comparison](https://bshp.io/articles/flash-tier-shootout-benchmark/),
[DeepSeek release benchmarks](https://api-docs.deepseek.com/updates/)

### Provider and ZDR decision matrix

“No training” and “zero data retention” are different claims. A provider may
retain abuse logs, metadata, or cached requests while still promising not to
train on prompts. A gateway’s ZDR filter also does not erase the provider’s
operational metadata or your own Pi/session logs.

| Provider/path | ZDR or retention posture | Recommendation for Pi |
|---|---|---|
| **OpenRouter** | Supports `zdr: true`, `data_collection: "deny"`, provider ordering, and allowlists. Upstream provider policy still applies; unrestricted fallback can defeat the privacy goal. | Best initial comparison layer. Use pinned model IDs, an explicit provider allowlist, and fail-closed routing for sensitive repositories. |
| **Groq** | Inference content is not retained by default; explicit data controls can disable reliability/abuse logging. Metadata and excluded products/features remain separate concerns. | Best direct low-cost/ZDR-oriented path for GPT-OSS 20B/120B and latency-sensitive work. |
| **Fireworks** | Public materials describe no training and no prompt/generation logging for qualifying open-model inference, but verify the exact endpoint and contractual terms. | Strong alternative for Qwen/DeepSeek if the selected endpoint is explicitly confirmed. |
| **Together AI** | Attractive catalogue and privacy controls, but do not infer universal ZDR from the open-weight model or the generic privacy page. | Excellent model/cost experiment; confirm account settings and endpoint terms before sensitive code. |
| **Mistral direct** | Explicit paid-plan ZDR for eligible stateless endpoints; stateful Agents, Files, and Conversations products are excluded. | Strongest European/ZDR-oriented option if approval and endpoint constraints are acceptable. |
| **Vercel AI Gateway** | Provides no-markup routing and ZDR-aware provider selection. The gateway and upstream terms remain separate; BYOK providers may need explicit compliance marking. | Good policy-controlled alternative to OpenRouter, especially if central routing and fallback rules matter. |
| **Hugging Face Inference Providers** | HF describes no storage of request bodies/responses but retains debugging logs and defers to the selected upstream provider. | Useful for experiments, not a blanket ZDR guarantee. Pin the actual upstream. |
| **DeepSeek direct** | Strong capability/price, but no clear direct API ZDR commitment was found; jurisdiction and privacy policy are material concerns. | Use for non-sensitive evaluation or through a qualifying ZDR intermediary. |
| **Alibaba Model Studio/Qwen direct** | Alibaba states Model Studio data is not used for training, but that is not a universal prompt-ZDR guarantee for every feature or region. | Good official Qwen control route; prefer explicit ZDR endpoints for sensitive code. |

Primary policy references: [OpenRouter routing](https://openrouter.ai/blog/insights/zero-data-retention/),
[Groq data controls](https://console.groq.com/docs/your-data),
[Fireworks privacy](https://fireworks.ai/privacy-policy),
[Mistral ZDR](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention/),
[Vercel secure AI Gateway](https://vercel.com/i/secure-ai-gateway),
[Hugging Face provider security](https://huggingface.co/docs/inference-providers/security),
[Alibaba Model Studio FAQ](https://www.alibabacloud.com/help/en/model-studio/faq-about-model-studio)

### Hosted-only Pi evaluation sequence

Start with the following provider/model pairs, rather than trying every model
through one unexamined gateway:

1. **OpenRouter with hard ZDR routing:** Qwen3.8-Flash, DeepSeek V4.1-Flash,
   GLM-5.3-Flash, and GPT-OSS 120B.
2. **Together Qwen3.8-Flash:** compare the same model against OpenRouter’s
   qualifying providers and measure tool-call/latency differences.
3. **DeepSeek direct `deepseek-flash`:** capability and price control test,
   restricted to non-sensitive repositories unless policy requirements are met.
4. **Groq GPT-OSS 120B and 20B:** fast direct/ZDR-oriented controls.
5. **Mistral Small 4 direct:** privacy/regional control comparison.
6. **Vercel AI Gateway:** compare its ZDR-aware routing and operational cost
   against OpenRouter.
7. **Gemini 3.8 Flash:** expensive reliability/capability baseline.

Measure successful tool-call rate, correction turns, time to a passing test,
context truncation, provider errors, cache hits, output tokens, and effective
cost per completed task. Never combine a ZDR requirement with unrestricted
automatic fallback: on a failed primary, fail or move only to an explicitly
approved ZDR provider.

## Cost scenarios

These examples assume **10M input tokens plus 2M output tokens**. They are not a
prediction of actual monthly use; coding agents can produce very different
ratios depending on context reuse, tool loops, and compaction.

| Path | Approximate cost for scenario |
|---|---:|
| Local llama.cpp | $0 marginal inference cost |
| Groq GPT-OSS 20B | $1.35 |
| DeepSeek `deepseek-flash` (V4.1-Flash) | $2.70 off-peak / $5.40 peak |
| Together GLM-5.3-Flash | $2.50 |
| Groq GPT-OSS 120B | $2.70 |
| Mistral Small | about $2.70 |
| Vercel Qwen3-Coder Next | about $7.40 |
| Gemini 3.8 Flash | $15.00 |

Formula:

```text
cost = input_tokens / 1,000,000 * input_price
     + output_tokens / 1,000,000 * output_price
```

For a Pi coding agent, output price matters disproportionately because every
tool call, plan, retry, and verification step produces output tokens.

## Alternatives to OpenRouter

OpenRouter is useful, but it is not the only way to get a multi-provider
catalogue.

| Alternative | What it provides | Cost/control | Recommendation |
|---|---|---|---|
| Direct Gemini/Together/Mistral/Groq/DeepSeek | One vendor, direct billing and policy | Usually clearest price and data terms | Preferred for the main hosted lane |
| Vercel AI Gateway | Managed catalogue, provider filtering, routing, spend visibility | Current catalogue advertises $5 monthly gateway credit and no token markup; upstream still matters | Best managed gateway alternative |
| Hugging Face Inference Providers | Multi-provider catalogue with provider selection and cheapest/preferred routing | Small free credit; exact cost depends on selected provider | Good experimentation alternative |
| Cloudflare AI Gateway | BYOK proxy, analytics, cache, rate limits, DLP/control features | Provider token rates pass through; not intrinsically cheaper | Use as a control plane, not as a model choice |
| Cloudflare Workers AI | Cloudflare-hosted open models | Very low entry cost, but small models may be inadequate for coding agents | Consider only after testing larger tool-capable models |
| Fireworks | Open-model serverless hosting and dedicated deployment path | $1 starter credit; model prices vary | Good if deployment control may matter later |
| OpenCode Zen/Go | Coding-focused balance/subscription | OpenCode Go currently advertises $10/month; usage is model/plan dependent | Interesting experiment, not a transparent cost benchmark |
| Direct local server | llama.cpp, Ollama, vLLM, LM Studio | No token billing; hardware-bound | Best privacy/default lane |

OpenRouter's current Standard plan lists a 5.5% platform fee, while its free
tier lists 25+ models and 50 requests/day. It can route to different upstream
providers, so model and provider must be pinned for reproducibility and data
control. [OpenRouter pricing](https://openrouter.ai/pricing), [provider API](https://openrouter.ai/docs/api/api-reference/providers/list-all-providers)

### OpenRouter model/provider discovery and fees

OpenRouter does provide API discovery for this use case, but it is split across
several endpoints. The most useful calls are:

```bash
# Models with at least one ZDR-capable endpoint; add price/provider/context filters.
curl 'https://openrouter.ai/api/v1/models?zdr=true&max_price=1&max_output_price=5&sort=pricing-low-to-high'

# Models filtered by the account's provider preferences, privacy settings,
# and guardrails. This requires an authenticated API key.
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  'https://openrouter.ai/api/v1/models/user'

# Current published ZDR endpoint list.
curl 'https://openrouter.ai/api/v1/endpoints/zdr'

# Providers and their privacy/terms metadata.
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  'https://openrouter.ai/api/v1/providers'

# Actual endpoints for one model, including provider, pricing, limits, and
# performance metadata. The endpoint API requires a management key.
curl -H "Authorization: Bearer $OPENROUTER_MANAGEMENT_KEY" \
  'https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints'
```

The important qualification is that `models?zdr=true` means “models with at
least one ZDR endpoint”; it does not mean that every provider serving each
returned model is ZDR. Use the per-model endpoint list and the live ZDR list to
inspect the actual route. OpenRouter documents `zdr=true` and
`data_collection=deny` as request-level routing controls:

```json
{
  "model": "qwen/qwen3.8-flash",
  "messages": [{"role": "user", "content": "Hello"}],
  "provider": {
    "zdr": true,
    "data_collection": "deny",
    "only": ["together", "fireworks"],
    "allow_fallbacks": false
  }
}
```

For sensitive work, the `only` list and `allow_fallbacks: false` matter: ZDR
does not make unrestricted fallback safe. OpenRouter still retains request
metadata such as model, cost, latency, and token counts, and Pi, extensions,
MCP tools, and terminal logs are separate retention surfaces. [OpenRouter model
API](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties),
[filtered model API](https://openrouter.ai/docs/api/api-reference/models/list-models-filtered-by-user-provider-preferences-privacy-settings-and-guardrails),
[endpoint ZDR guidance](https://openrouter.ai/blog/insights/zero-data-retention/)

The fee model is also worth separating:

| OpenRouter path | Additional cost | Practical implication |
|---|---:|---|
| Standard prepaid credits | Current pricing page lists a **5.5% platform fee on the pay-as-you-go plan**; taxes/payment-specific charges may also apply | A $100 credit purchase is approximately $105.50 before any tax or checkout-specific charge. The checkout total is authoritative. |
| BYOK | Current plan includes an allowance; after it, OpenRouter charges **5% of equivalent list-price inference** from OpenRouter credits | BYOK avoids paying the model provider through OpenRouter, but it is not permanently free routing. Prevent shared-provider fallback if you need cost or privacy control. |
| Business | Current pricing page lists **8%**, so it is not attractive for this individual low-cost use case | Enterprise/contract terms may differ. |
| Direct provider | No OpenRouter fee; provider billing and any provider payment/credit terms apply | Usually the best default when one provider has the model and policy you want. |

The fee is significant at small spend levels because it is charged on the
credit purchase rather than only on consumed tokens. Avoid large prepayments
until the model/provider route is proven.

### Lower-fee alternatives to OpenRouter

| Route | Models to try | Billing/fee posture | Recommendation |
|---|---|---|---|
| **Together direct** | Qwen3.8-Flash, GLM-5.3-Flash, DeepSeek, GPT-OSS | No separately published OpenRouter-style gateway surcharge; prepaid provider credits | Best direct low-cost route for the current Qwen/GLM shortlist. Confirm account privacy controls before sensitive use. |
| **Groq direct** | GPT-OSS 20B/120B | No published platform surcharge; payment method and usage billing rather than OpenRouter credits | Best fast direct route and a useful ZDR-oriented control. |
| **Fireworks direct** | Qwen, DeepSeek, GPT-OSS, Kimi, other open models | No separately published gateway surcharge; per-model serverless/dedicated rates | Strong alternative when the exact endpoint’s ZDR and region are confirmed. |
| **Mistral direct** | Mistral Small 4 and other Mistral models | Direct pay-as-you-go/prepaid provider billing | Best European/ZDR-oriented route, subject to paid-plan/stateless endpoint requirements. |
| **Vercel AI Gateway** | Provider-dependent catalogue | No token markup; currently advertises an initial monthly credit; provider and payment terms still apply | Good policy/routing alternative if its free credit and ZDR-aware routing offset the extra intermediary. |
| **Hugging Face Inference Providers** | Provider-dependent catalogue | No markup over provider rates; small account/Pro credits | Useful discovery layer, but pin the upstream provider: HF’s own retention policy does not automatically make the upstream ZDR. |

My current billing recommendation is therefore: use **Together direct** for
Qwen3.8-Flash and GLM-5.3-Flash, **Groq direct** for GPT-OSS, and **Fireworks
or Mistral direct** where their exact privacy/region terms fit. Use OpenRouter
when its ZDR filtering, model coverage, or routing convenience is worth the
5.5% credit fee—not as the default path for every request. [OpenRouter pricing](https://openrouter.ai/pricing),
[BYOK documentation](https://openrouter.ai/docs/guides/overview/auth/byok),
[Together pricing](https://www.together.ai/pricing),
[Groq billing](https://console.groq.com/docs/billing-faqs),
[Fireworks pricing](https://fireworks.ai/pricing),
[Vercel AI Gateway pricing](https://vercel.com/docs/ai-gateway/pricing),
[Hugging Face provider pricing](https://huggingface.co/docs/inference-providers/pricing)

## Data retention and training policies

The important distinction is between:

- **training use:** whether prompts may be used to improve models;
- **operational retention:** logs retained for abuse prevention, debugging, or
  billing;
- **routing exposure:** how many upstream processors receive the request;
- **your own retention:** Pi sessions and provider logs may persist locally or in
  the provider account even if the provider advertises no training.

| Provider/path | Practical policy posture for repository code |
|---|---|
| Local llama.cpp | Strongest boundary if the server is local and telemetry/logging are controlled. No provider receives the prompt. |
| Gemini paid API | Google states paid API content is not used to improve products. Free-tier content has different terms and should not be treated as equivalent. |
| Mistral | Potentially strong EU/ZDR option, but ZDR is eligibility/endpoint dependent. Regional processing is not itself a retention guarantee. |
| Groq | Provider documentation describes no inference-content retention by default, with optional ZDR controls; verify current account terms. |
| Cerebras | Public materials state strong no-retention handling, but verify the direct product/account terms before treating it as contractual. |
| Together | Check current account controls and terms for the selected endpoint; do not infer ZDR from hosting an open model. |
| Fireworks | Check current DPA and endpoint policy. Use explicit stateless settings where supported; do not assume all endpoints have identical retention. |
| DeepSeek | Treat as unsuitable for sensitive repositories until current API terms clearly meet the required training/retention standard. |
| OpenRouter | The upstream provider may change under fallback routing. Apply provider allowlists and data-policy/ZDR filters where available; otherwise it is not a dependable privacy boundary. |
| Vercel AI Gateway | Gateway logs and the selected upstream provider are separate concerns. Pin provider/model and inspect the live model metadata and provider terms. |
| Hugging Face Providers | Policy depends on the selected inference provider. Provider pinning is essential. |
| Cloudflare AI Gateway | Cloudflare may provide control/logging features, but upstream provider retention still applies when BYOK or pass-through routing is used. |
| OpenCode Go/Zen | Treat as an intermediary subscription service; inspect current terms before sending proprietary code. |

For high-sensitivity work, the preferred order is local llama.cpp, then a direct
provider with explicit paid no-training/ZDR terms, then a pinned gateway route.
Avoid free-tier or automatic-fallback routes for secrets, credentials, or
proprietary source.

## Suggested Pi portfolio

| Tier | Model/path | Use |
|---|---|---|
| 0 | OpenRouter with hard ZDR routing | Controlled hosted comparison layer; pin providers and fail closed |
| 1 | Qwen3.8-Flash or DeepSeek `deepseek-flash` | First-tier low-cost coding/agent evaluation; strong reported agent results and long context |
| 2 | Together GLM-5.3-Flash | Strong cheap hosted coding and review comparison point |
| 3 | Groq GPT-OSS 20B/120B | Fast direct/ZDR-oriented path for triage and inexpensive retries |
| 4 | Mistral Small 4 direct | European paid-ZDR alternative for supported stateless endpoints |
| 5 | Gemini 3.8 Flash | Difficult multi-file work and reliable hosted tool-loop baseline |
| 6 | Existing Claude/OpenAI subscriptions through Pi | Frontier escalation without API billing |
| Separate boundary | Local Devstral Small 2 or Qwen3.5 9B | Private edits and work that should not leave the machine |

The first hosted experiment should compare six model/provider pairs: Qwen3.8-
Flash through OpenRouter ZDR routing, Qwen3.8-Flash through Together, DeepSeek
`deepseek-flash` direct, GLM-5.3-Flash through Together, GPT-OSS 120B through
Groq, and Gemini 3.8 Flash direct. Add Mistral Small 4 and Fireworks after the
first pass if ZDR and regional requirements make them relevant.
Use the same repository tasks and record tool-call success, correction count,
latency, input/output tokens, and total cost. Add providers only when the
results justify the extra policy and credential surface.

### Three sensible starting configurations

These are deliberately different choices rather than a single ranking:

| Configuration | Start with | Why choose it | What you give up |
|---|---|---|---|
| **Privacy-first** | Local Devstral Small 2 24B; fall back to local Qwen3.5 9B; use a direct paid provider only for hard problems | Repository contents and tool results can stay inside the local machine, and recurring token cost is zero | Hardware, electricity, model downloads, latency, and weaker long-horizon reliability than the best hosted models |
| **Lowest-cost hosted** | Groq GPT-OSS 20B for fast small tasks; Together GLM-5.3-Flash, Qwen3.8-Flash, or DeepSeek `deepseek-flash` for cheap bulk work | Low measured token rates and simple OpenAI-compatible connections; good for triage, review, tests, and bounded edits | More correction/retry risk, changing catalogues, and provider-specific privacy caveats |
| **Balanced hosted default** | OpenRouter with hard ZDR routing for Qwen/DeepSeek/GLM; Together Qwen3.8-Flash as a direct comparison; Gemini 3.8 Flash for escalation | Keeps most spending near the cheap end while preserving provider controls and a more capable hosted escalation path | Requires provider allowlists, multiple credentials, and careful interpretation of ZDR; Gemini’s output price is materially higher |
| **Capability-first without API-heavy frontier billing** | Gemini 3.8 Flash as the hosted default; local model for sensitive work; existing Claude/OpenAI subscriptions for exceptional escalation | Gives the strongest first hosted baseline in this survey while avoiding routine Anthropic/OpenAI API metering | Higher cost than open-model hosts and continued dependence on a provider’s changing model/pricing policy |

My recommendation for this phase is **Balanced hosted default**. It has the best cost/capability/privacy shape while keeping the work non-local: enforce ZDR routing at the gateway, compare Qwen3.8-Flash and DeepSeek against GLM, and reserve Gemini for escalation. Choose **Privacy-first** instead if code must remain on the machine; choose **Lowest-cost hosted** if the main goal is experimentation; choose **Capability-first** if failed tool loops cost more than the additional tokens.

Do not select a provider solely from the input-token price. For agentic coding, compare the complete task cost: output tokens, retries, malformed tool calls, latency, and the amount of human correction. A $0.15/$0.50 model that completes a task in one pass can be cheaper in practice than a $0.075/$0.30 model that needs several repair loops.

## Implemented starting point

The repository now includes a portable [hosted-provider discovery helper](../artifacts/pi-hosted-provider-discovery.py)
and a [Pi hosted-provider runbook](../artifacts/pi-hosted-provider-runbook.md).
The helper is read-only, uses only Python's standard library, does not contain
credentials, and captures OpenRouter's live ZDR-capable model/endpoint view.
The runbook keeps actual keys and machine-specific Pi configuration at user
scope, gives a direct-provider template, and defines a minimal tool-call smoke
test before a model is trusted with real repositories.

The first execution is recorded in the [Pi connectivity run](pi-connectivity-run-20260921.md):
the public OpenRouter discovery returned 239 ZDR-eligible models, while the
local llama.cpp route passed both text and read-only tool-loop probes using the
currently loaded Qwen3.6 model. Hosted Pi probes remain pending until a
provider credential is configured outside the repository.

## Sources

- [Pi providers](https://pi.dev/docs/latest/providers)
- [Pi custom models](https://pi.dev/docs/latest/models)
- [Pi llama.cpp documentation](https://pi.dev/docs/latest/llama-cpp)
- [llama.cpp](https://github.com/ggml-org/llama.cpp)
- [Together pricing](https://www.together.ai/pricing)
- [Groq models](https://console.groq.com/docs/models)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini latest model details](https://ai.google.dev/gemini-api/docs/latest-model)
- [Mistral pricing](https://mistral.ai/pricing/)
- [Fireworks pricing](https://fireworks.ai/pricing)
- [OpenRouter pricing](https://openrouter.ai/pricing)
- [OpenRouter provider metadata](https://openrouter.ai/docs/api/api-reference/providers/list-all-providers)
- [Vercel AI Gateway pricing](https://vercel.com/docs/ai-gateway/pricing)
- [Hugging Face Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing)
- [Cloudflare Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [OpenCode Go](https://dev.opencode.ai/docs/go/)

## Caveats

This report is a current research snapshot, not a contractual statement of
provider policy. Prices, model names, quotas, retention terms, tool support, and
regional availability can change without a Pi release. Before adoption, fetch
the live provider catalogue, confirm the model's function-calling behavior in Pi,
and review the current provider terms for the exact endpoint and account tier.
