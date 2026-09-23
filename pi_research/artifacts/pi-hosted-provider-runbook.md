# Pi hosted-provider runbook

This runbook configures Pi to compare hosted providers without putting API
keys or machine-specific settings in a project repository. It is designed for
the lower-cost, non-frontier model lane described in the companion landscape
report.

The companion [provider and model landscape](../notes/pi-llm-provider-and-model-landscape-20260921.md)
contains the research rationale; the [connectivity run](../notes/pi-connectivity-run-20260921.md)
contains the latest observed results. The command examples below assume the
current working directory is the project root; when copying this runbook to a
different project, replace the relative paths accordingly.

## 1. Discover current candidates

The discovery helper is read-only. It asks OpenRouter for models with at least
one ZDR-capable endpoint and applies a cheap price ceiling. The result is a
dated snapshot, not a guarantee that every provider route for a model is ZDR.

Before a provider test, record the installed Pi version and perform a
non-mutating readiness check:

```bash
pi --version
pi auth check --provider "$PI_PROVIDER" --model "$PI_MODEL" --no-refresh --json
```

The readiness check must resolve credentials and the selected model without an
authentication or catalogue error. Do not use `--credentials` in shared logs.

```bash
python3 artifacts/pi-hosted-provider-discovery.py \
  --max-input 1 --max-output 5 > .scratch/runs/openrouter-zdr.json

# Optional account-specific privacy/provider filtering:
export OPENROUTER_API_KEY='...'
python3 artifacts/pi-hosted-provider-discovery.py --account \
  > .scratch/runs/openrouter-account.json
```

For sensitive repositories, inspect the actual endpoint/provider list and use
an explicit provider allowlist with `allow_fallbacks: false`. The public
`zdr=true` model query means that at least one qualifying endpoint exists; it
does not mean that arbitrary fallback is compliant.

## 2. Configure direct providers in Pi

Keep the following in the user-level Pi configuration, normally
`~/.pi/agent/models.json`, and substitute the current model IDs and prices from
the provider's live catalogue. Do not commit this file or its keys.

```json
{
  "providers": {
    "together-direct": {
      "baseUrl": "https://api.together.xyz/v1",
      "api": "openai-completions",
      "apiKey": "$TOGETHER_API_KEY",
      "models": [
        {
          "id": "Qwen/Qwen3.8-Flash",
          "contextWindow": 1000000,
          "cost": { "input": 0.15, "output": 0.47 }
        }
      ]
    },
    "groq-direct": {
      "baseUrl": "https://api.groq.com/openai/v1",
      "api": "openai-completions",
      "apiKey": "$GROQ_API_KEY",
      "models": [
        {
          "id": "openai/gpt-oss-20b",
          "contextWindow": 131072,
          "cost": { "input": 0.075, "output": 0.30 }
        }
      ]
    }
  }
}
```

Pi's exact custom-model schema and provider-specific model IDs can change. Pi
resolves `$ENV_VAR` API-key values at request time; the variables must exist in
the process environment and the file must remain user-level. Use
the current [Pi custom model documentation](https://pi.dev/docs/latest/models)
as the authority before copying this template. If a provider's OpenAI
compatibility is partial, add only the compatibility flags that its live
documentation requires.

## 3. Existing local llama.cpp route

The current local server is configured at `http://127.0.0.1:8642/v1`. A
read-only model-list request should be used before selecting a model:

```bash
curl -fsS http://127.0.0.1:8642/v1/models > .scratch/runs/llamacpp-models.json
```

On the 21 September 2026 run, the server advertised seven models and reported
`Qwen3.6-35B-A3B-UD-Q4_K_M` as loaded. The configured
`gpt-oss-20b-MXFP4` was advertised by Pi but was not loaded by llama.cpp. The
loaded Qwen model passed Pi’s text and read-only tool probes. Loading or
switching models remains an explicit server operation and is not performed by
this runbook.

## 4. Use OpenRouter as a controlled comparison route

For a ZDR comparison route, the request body should include the equivalent of:

```json
{
  "provider": {
    "zdr": true,
    "data_collection": "deny",
    "only": ["together", "fireworks"],
    "allow_fallbacks": false
  }
}
```

The provider names and model ID must be checked against the live endpoint
response. If Pi's provider configuration cannot express these per-request
controls, put OpenRouter behind a small local adapter or use a direct provider
for sensitive work. Do not assume a global account preference is equivalent to
a fail-closed request route.

Pi can express the OpenRouter route directly for a built-in or custom model via
`compat.openRouterRouting`. A minimal per-model override is:

```json
{
  "providers": {
    "openrouter": {
      "modelOverrides": {
        "qwen/qwen3.8-flash": {
          "compat": {
            "openRouterRouting": {
              "zdr": true,
              "data_collection": "deny",
              "only": ["together", "fireworks"],
              "allow_fallbacks": false
            }
          }
        }
      }
    }
  }
}
```

Pi sends this object as OpenRouter's `provider` request field. Keep the
provider allowlist narrow and update it from live endpoint discovery; `order`
alone is only a preference and is not fail-closed.

## 5. Smoke-test each route before agent use

Use a disposable repository and verify, in order:

1. Pi can list/select the model and complete a streaming response.
2. A tool call is emitted with valid JSON and the tool result is accepted.
3. A two-step edit/test task completes without manual repair.
4. Token usage, latency, and provider/model IDs are visible in the session log.
5. The provider's current retention/training terms match the repository class.

For a reproducible read-only probe, Pi's current CLI supports:

```bash
pi --list-models "$PI_MODEL"
pi --provider "$PI_PROVIDER" --model "$PI_MODEL" \
  --no-session --no-context-files --no-skills --no-extensions \
  --tools read,grep,find,ls -p \
  'List the files in the current directory in one sentence. Do not edit, create, delete, or execute files.'
```

The first command checks catalogue/auth visibility; the second checks the
agent/tool loop without granting write or shell tools. Record the exact model,
provider, Pi version, latency, token usage, and any routing metadata.

These probes establish connectivity and read-only tool use only. They do not
prove reliable streaming metrics, edit correctness, test execution, multi-turn
completion, hosted-provider retention, or cost under a real task. Qualify those
separately before promoting a route to a default.

Record total task cost, not only input price:

```text
cost = input_tokens / 1_000_000 * input_price
     + output_tokens / 1_000_000 * output_price
```

Start with Together Qwen3.8-Flash and GLM-5.3-Flash, Groq GPT-OSS 20B, and an
OpenRouter ZDR-pinned equivalent. Add DeepSeek `deepseek-flash` for capability
and price comparison only after deciding whether its direct privacy posture is
acceptable. Keep local llama.cpp as the private boundary.
