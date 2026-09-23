# Pi connectivity run

**Run date:** 21 September 2026  
**Pi:** 0.86.1  
**Purpose:** read-only validation of the discovery helper, local llama.cpp
connectivity, and hosted-provider readiness.

Related documents: [provider and model landscape](pi-llm-provider-and-model-landscape-20260921.md),
[earlier connectivity research](llm-connectivity-research-20260921.md), and the
[hosted-provider runbook](../artifacts/pi-hosted-provider-runbook.md).

## Results

| Check | Result | Evidence |
|---|---|---|
| OpenRouter public discovery via `uv` | Pass | 239 models with at least one ZDR-capable endpoint; 873 endpoint records |
| Pi provider credentials | Not configured | `pi auth check --no-refresh --json` returned `credentials_not_configured` for OpenRouter, Together, Groq, Fireworks, Mistral, Google, and DeepSeek |
| Local llama.cpp server | Reachable | `http://127.0.0.1:8642/v1/models` returned seven model entries |
| Local Pi text probe | Pass | Loaded `Qwen3.6-35B-A3B-UD-Q4_K_M` returned `PI_LOCAL_CONNECTIVITY_OK` |
| Local Pi read-only tool probe | Pass | Pi produced a directory listing using only `read,grep,find,ls` |
| Hosted Pi smoke tests | Not run | No provider API keys or stored Pi credentials are present |

The raw public discovery response is in
`.scratch/runs/openrouter-zdr.json`; local probe outputs are in
`.scratch/runs/` and are intentionally not treated as provider credentials or
durable configuration.

## Live hosted candidates

The public query used:

```text
GET /api/v1/models?zdr=true&max_price=1&max_output_price=5&sort=pricing-low-to-high
```

Representative current entries from that response, with prices normalized to
USD per million tokens:

| OpenRouter model ID | Input | Output | Context | Comment |
|---|---:|---:|---:|---|
| `qwen/qwen3.8-27b:free` | 0 | 0 | 262k | Free route; investigate quota and provider before relying on it |
| `openai/gpt-oss-20b` | $0.03 | $0.13 | 131k | Cheapest paid serious candidate in this snapshot |
| `z-ai/glm-5.3-flash` | $0.09 | $0.30 | 1.31M | Strong low-cost coding/review candidate |
| `deepseek/deepseek-v4.1-flash` | $0.15 | $0.60 | 1.05M | First-tier capability/price candidate |
| `qwen/qwen3.8-27b` | $0.20 | $2.50 | 1M | Paid Qwen route; output pricing is materially higher than the free route |
| `mistralai/mistral-small-2603` | $0.15 | $0.60 | 262k | Mistral Small 4 route |
| `openai/gpt-oss-120b` | $0.15 | $0.60 | 131k | Larger open-model comparison point |

These are catalogue observations, not guarantees that every provider serving a
model is ZDR. The helper also captured the endpoint-level ZDR list; use the
provider allowlist and `allow_fallbacks: false` before sending sensitive code.

## Local finding

The local llama.cpp server had `Qwen3.6-35B-A3B-UD-Q4_K_M` loaded. Pi’s
configured `gpt-oss-20b-MXFP4` was present in the Pi model configuration but the
server returned `model is not loaded` when selected. The correct next local
action is either to select the loaded Qwen model or load the desired model in
llama.cpp; this run did not alter the server.

The local probes establish endpoint reachability, text generation, and one
read-only tool loop only. They do not establish reliable streaming metrics,
edit/test correctness, multi-turn completion, hosted-provider retention, or
production cost. The model-generated file count in the probe output is not
treated as benchmark evidence; only the successful qualitative listing is
recorded.

## Next credentialed test

After configuring one provider key outside the repository, run the runbook’s
readiness check and read-only smoke test for one exact live model. Start with
Together Qwen/GLM or Groq GPT-OSS, then compare the same model through a
fail-closed OpenRouter route. Keep the first request small and non-sensitive.
