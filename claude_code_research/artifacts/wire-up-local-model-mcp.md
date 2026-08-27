# Prompt: wire up a non-Anthropic model as a project-scoped MCP tool

Paste the block below into a Claude Code session running in the target
project's directory. It registers an "ask another model" tool — backed by a
local llama.cpp/Ollama server or a hosted aggregator like OpenRouter — as an
MCP server scoped to that one project only. Claude stays the primary driver
of the session; the other model is just a tool Claude (or you, explicitly)
can call for a specific job.

Scope note: this uses Claude Code's **local** MCP scope (`claude mcp add
--scope local`), which is private to you and tied to this one project
directory — it is stored in `~/.claude.json` under that project's entry, not
checked into the repo, and does not sync to other machines or teammates. Use
`--scope project` instead only if you deliberately want to check a
`.mcp.json` into the repo and share this with collaborators (rare for a
personal local-model setup).

---

## Prompt

```
I want to add a project-scoped MCP tool that lets me delegate specific jobs
to a non-Anthropic model (local or hosted) from within this Claude Code
session, without changing which model drives the session overall.

Do this:

1. Ask me which backend to wire up, if not already told:
   - Local llama.cpp server (llama-server, OpenAI-compatible /v1 endpoint)
   - Local Ollama
   - OpenRouter (hosted, needs an API key)
   - Some other OpenAI-compatible endpoint I specify

2. Confirm the concrete connection details before installing anything:
   - base_url (e.g. http://localhost:8080/v1 for llama-server,
     http://localhost:11434/v1 for Ollama, https://openrouter.ai/api/v1
     for OpenRouter)
   - model name as the backend expects it
   - API key if the backend needs one (empty/dummy string is fine for a
     local server that doesn't check it)

3. If the backend is a local server (llama-server/Ollama) and nothing is
   listening on that port yet, tell me plainly rather than assuming — do
   not silently skip verification. Check with a plain curl to
   `<base_url>/models` or equivalent before proceeding, and stop to ask if
   it's not reachable.

4. Install pal-mcp-server (https://github.com/BeehiveInnovations/pal-mcp-server)
   via uvx — it's the best-maintained option that accepts an arbitrary
   OpenAI-compatible base_url (via CUSTOM_API_URL) rather than being locked
   to a single named provider. Don't substitute a narrower single-purpose
   wrapper unless I've asked for one by name.

5. Register it at LOCAL scope for this project only:
     claude mcp add --scope local <name> -- uvx pal-mcp-server
   with CUSTOM_API_URL / CUSTOM_MODEL_NAME / CUSTOM_API_KEY set to the
   values confirmed in step 2. Do not use --scope project (which would
   check a .mcp.json into the repo and share this with anyone who clones
   it) or --scope user (which would make it available in every project on
   this machine) unless I explicitly ask for one of those instead.

6. Verify the registration: run `claude mcp list` (or the current
   equivalent) and confirm the new server shows up and connects. Report
   back the scope and connection status plainly — don't declare success
   without checking it actually connects.

7. Tell me the exact tool name Claude will see so I know what to reference
   when I want to delegate a job to it (e.g. "use <tool> for this one").

Stop and ask me before doing anything destructive or before installing
system-wide packages — uvx-managed installs and this project's local MCP
scope are fine to do without re-confirming once I've answered step 1-2.
```

---

## Why this shape

- MCP is a tool-calling layer, not an alternate inference backend — this
  wires up "Claude can call another model as a tool," not "swap what model
  runs the session." See `notes/` in this repo (or ask a fresh session to
  research it) if `ANTHROPIC_BASE_URL` / Claude Code Router style
  session-wide or category-wide routing is what's actually wanted instead.
- `pal-mcp-server` was chosen over Ollama-specific or llama.cpp-specific
  wrappers because it takes an arbitrary OpenAI-compatible `base_url`, so
  the same setup works whether the backend is llama-server, Ollama, or a
  hosted aggregator — one tool, three backend options, no rewrite between
  them.
- Local scope keeps this out of git and out of other machines by default,
  since a locally-running model endpoint is almost never something you want
  a teammate's Claude Code session to depend on.
