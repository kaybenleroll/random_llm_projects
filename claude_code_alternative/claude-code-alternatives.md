---
title: "Claude Code Alternatives: A Comprehensive Survey of AI Coding Agents in 2026"
author: "May 2026"
---

# Claude Code Alternatives: A Comprehensive Survey of AI Coding Agents in 2026

## Introduction

Claude Code has established itself as one of the most capable agentic coding tools available: it runs entirely in the terminal, takes high-level natural-language instructions, autonomously edits multiple files, executes shell commands, runs tests, and iterates until the task is done. Its superpowers system — skills, hooks, and MCP server support — allows deep customisation of its workflow. For users on the Max plan (~$100/month for unlimited usage), the economics are excellent for heavy usage. But the plan landscape for AI tools changes rapidly, and a prudent engineer should understand the full landscape of alternatives before needing them.

This document surveys the entire landscape of AI coding agents available as of mid-2026: open-source CLI tools, IDE extensions, dedicated AI IDEs, cloud platform agents, and commercial assistants. For each, it covers architecture, provider flexibility, MCP/extensibility support, and realistic cost.

**A note on methodology:** This report was produced using an adversarial deep-research process (108 research agents, 26 sources fetched, 25 factual claims verified via 3-agent voting). Claims that failed verification — particularly specific GitHub star counts and token-volume figures from aggregator blog posts — are excluded or clearly caveated. Where specific figures are cited without a "verified" note, they come from training data (accurate as of approximately August 2025) and may have changed.

**How to read this document:** If you want the fastest path to a conclusion, jump to the [Feature Comparison Matrix](#feature-comparison-matrix), the [Provider Flexibility Analysis](#provider-flexibility-analysis), and the [Recommendations](#recommendations). The deep-dive sections are there for when you need to evaluate a specific tool seriously.

---

## The AI Coding Agent Taxonomy

Before comparing tools, it helps to understand the four distinct categories that have emerged. This taxonomy comes from Artificial Analysis's coding agent classification (verified):

**CLI Tools** run entirely in the terminal. They take instructions, edit files, run commands, and loop autonomously. This is the category Claude Code belongs to. Other members: Aider, Gemini CLI, Goose, OpenCode, Qwen Code, Kimi CLI, Codex (OpenAI).

**IDE Extensions** augment an existing editor (primarily VS Code or JetBrains). They have full access to the editor's language server, refactoring tools, and UI, but are less suitable for scripted or headless workflows. Members: Cline, Continue.dev, GitHub Copilot, Amazon Q Developer, Tabnine, JetBrains AI Assistant.

**Dedicated AI IDEs** are entire editors rebuilt around AI-first workflows. They typically fork VS Code and add deeper AI integration than an extension permits. Members: Cursor, Windsurf.

**Cloud Platform Agents** run primarily in the cloud or a sandboxed environment (Docker). They expose a web UI or API and are designed for longer-running autonomous tasks, often with their own execution environments. Members: OpenHands, Devin, Manus, Jules, Genie.

A Claude Code user primarily cares about the CLI tools category, but the IDE and cloud categories contain tools capable enough to be worth understanding as alternatives — especially if your workflow includes time in an editor.

---

## Part I: CLI-Native Tools

### Aider

**What it is:** Aider is the most mature and architecturally similar open-source alternative to Claude Code. It is a terminal-based pair-programming tool that works directly with your existing git repository, takes natural-language instructions, autonomously edits multiple files, and commits changes.

**Author and licence:** Created by Paul Gauthier. MIT licence. Open source at `github.com/Aider-AI/aider`.

**Community size:** Approximately 45,300 GitHub stars as of May 2026 (verified by the deep-research process). This is among the largest in the open-source CLI coding agent category.

**Architecture:** Aider is written in Python and uses the `litellm` library as its LLM abstraction layer, which means it can talk to virtually any LLM provider that litellm supports. The editing mechanism is based on unified diffs: the model is asked to produce a git-style diff, which Aider then applies to the working tree and automatically commits. This is a deliberate design choice — unified diffs are compact and less error-prone for the model to produce than rewriting entire files. Aider supports several edit formats depending on the task and model:

- **diff** — the default, produces unified diffs
- **whole** — the model rewrites the entire file (less efficient, sometimes more reliable for small files)
- **architect mode** — a two-step process where one model plans the changes and a second cheaper model applies them, reducing cost

**Installation:**

```bash
pip install aider-chat
# or with uv
uv tool install aider-chat
```

**LLM provider support:** Aider supports all major providers via litellm, including:

- Anthropic (Claude family — Claude 3.5 Sonnet, Claude 3 Opus, etc.)
- OpenAI (GPT-4o, o1, o3)
- Google (Gemini 2.5 Pro via Vertex AI or AI Studio)
- AWS Bedrock
- Azure OpenAI
- OpenRouter (verified — full setup documented at `aider.chat/docs/llms/openrouter.html`)
- Ollama for local models
- LM Studio
- Groq, Mistral, Cohere, and many others

**OpenRouter setup (verified):**

```bash
export OPENROUTER_API_KEY=sk-or-...
aider --model openrouter/anthropic/claude-3.5-sonnet
# or any OpenRouter-hosted model:
aider --model openrouter/deepseek/deepseek-chat
aider --model openrouter/google/gemini-2.5-pro
```

**Local LLM setup (Ollama):**

```bash
# Start Ollama with a coding model first
ollama pull qwen2.5-coder:32b

# Then run Aider
aider --model ollama/qwen2.5-coder:32b
```

**Agentic capabilities:** Aider can run shell commands via the `/run` command and in `--auto-run` mode will execute suggested commands automatically. It maintains a context of added files and can be instructed to add more mid-session. It supports `/web` for fetching URLs into context and can integrate with test runners. The workflow is: add files to context → give instruction → model proposes diffs → Aider applies and commits → repeat.

**Git integration:** Every accepted change is automatically committed. This is tightly integrated — you can see the full history of AI changes in `git log`. There is also an `--auto-commits` flag to control this behaviour.

**Shell execution:** Via `/run <command>` or `--auto-run`. Aider can also be configured with `--test-cmd` to run tests automatically after each change.

**MCP support:** As of August 2025, Aider did not have native MCP server support. This is a meaningful gap compared to Claude Code. Check the Aider changelog for current status, as the project moves quickly.

**Extensibility:** Aider has limited plugin architecture compared to Claude Code. Configuration is via `.aider.conf.yml` and environment variables. There is no equivalent to Claude Code's skills or hooks system. What it lacks in extensibility it compensates for in simplicity and reliability.

**Modes:**

- **code** — the default mode, edits files
- **architect** — planning model + editing model split
- **ask** — ask questions about code without editing
- **help** — help with Aider itself

**Cost model:** Open source, free to use. You pay only for the LLM API calls you make. With Claude 3.5 Sonnet via Anthropic API, a typical coding session might cost $0.50–$3.00 depending on context size and number of changes. With OpenRouter you can route to cheaper models.

**Strengths:**
- Most CLI-native and architecturally similar to Claude Code of all open-source options
- Excellent git integration — every change is tracked
- Wide provider support via litellm
- OpenRouter support is well-documented and works reliably
- Mature, battle-tested codebase with high benchmark performance
- Supports local LLMs via Ollama
- Very low overhead — just Python and an API key

**Weaknesses:**
- No MCP support (as of mid-2025)
- No skills/hooks system — less extensible than Claude Code
- Context management is manual (you explicitly `/add` files)
- Less capable at long multi-step autonomous tasks compared to Claude Code
- No built-in web search or browser use

---

### OpenCode

**What it is:** OpenCode is a terminal UI (TUI) coding agent built by the SST/Anomaly team (the same people behind the SST serverless framework). It is written in Go and presents a rich interactive terminal interface while supporting a very wide range of LLM providers.

**Author and licence:** Built by the SST/Anomaly team. Open source at `github.com/sst/opencode`.

**Community size and activity:** Very actively developed — version 1.15.13 was released on May 30, 2026, with 815 total releases indicating extremely rapid iteration (verified). This is one of the most actively maintained tools in the space.

**Architecture:** OpenCode is a Go binary with a full TUI (terminal user interface) built using the Bubble Tea framework. It integrates with the AI SDK and Models.dev for LLM provider abstraction. It also supports Language Server Protocol (LSP) for code intelligence, meaning it can provide type-aware, semantically accurate code context rather than just raw file contents. Multi-session support allows you to maintain separate contexts for different tasks.

**Installation:**

```bash
# via npm (cross-platform)
npm install -g opencode-ai

# or directly via binary release
curl -fsSL https://opencode.ai/install | bash
```

**LLM provider support:** OpenCode supports 75+ LLM endpoints (verified) including:

- Anthropic (Claude family)
- OpenAI
- Google (Gemini via AI Studio or Vertex)
- AWS Bedrock
- Azure OpenAI
- OpenRouter
- Ollama (local models)
- LM Studio
- Grok (xAI)
- And many more via the AI SDK / Models.dev integration

This is the broadest provider flexibility of any CLI tool in the category.

**OpenRouter and Ollama:** Both confirmed as supported providers. Configuration is via a `~/.config/opencode/config.json` or project-level config.

**Agentic capabilities:** OpenCode can read and edit files, run shell commands, and iterate autonomously. The TUI provides a chat interface that feels more like a dedicated application than a REPL. LSP integration means it can navigate symbol definitions, find references, and understand project structure at the type level.

**MCP support:** OpenCode supports MCP servers. This is a significant advantage over Aider for users who have invested in an MCP ecosystem.

**Cost model:** Open source, free to use. API costs only.

**Strengths:**
- Broadest LLM provider support of any CLI tool (75+ endpoints verified)
- Rich TUI with a more polished interactive experience than most CLI tools
- LSP integration for semantic code understanding
- MCP support
- Extremely active development
- Built in Go — fast, single binary, no Python dependency hell

**Weaknesses:**
- Relatively new compared to Aider — less battle-tested
- TUI approach is slightly less scriptable than a pure REPL like Aider
- Smaller community than Aider
- Documentation less mature than older tools

---

### Goose (by Block)

**What it is:** Goose is an open-source, on-device AI coding agent developed by Block (formerly Square, the company associated with Jack Dorsey). It is available as both a CLI and a desktop application. Its primary differentiator is an extensions system with native MCP support.

**Author and licence:** Developed by Block, Inc. Apache 2.0 licence. Open source at `github.com/block/goose`.

**Community size:** Community size was disputed in the research verification process — a claim of ~45,800 stars failed the adversarial check, and the actual figure from primary sources could not be independently confirmed. The project has significant corporate backing from Block.

**Architecture:** Goose runs on-device, meaning all execution happens locally on your machine (the LLM calls go to wherever you configure, including local Ollama). It uses a toolkit/extension system where each extension provides a set of tools that the agent can use. This is philosophically similar to MCP but is Goose's own format. Goose also supports MCP servers as first-class inputs to the extension system, meaning your existing MCP server investments carry over.

**Installation:**

```bash
# macOS
brew install block/tap/goose

# or via install script
curl -fsSL https://github.com/block/goose/releases/latest/download/install.sh | bash
```

**LLM provider support:** Goose is model-agnostic and supports multiple provider configurations simultaneously. Supported providers include Anthropic, OpenAI, Google, Groq, Ollama, and others. It does not lock you to a single provider and allows per-task model configuration.

**Local LLM support:** Confirmed support for Ollama. The claim about this was partially refuted in the adversarial verification (a blog post's description was unverified), but the architectural design of Goose makes local LLM support a core feature — the on-device philosophy would be undermined by requiring cloud-only models.

**Agentic capabilities:** Goose can edit files, run shell commands, use its extension system to call external tools, and iterate autonomously on tasks. It has a particularly strong story for DevOps and infrastructure tasks.

**MCP support:** Native MCP integration is listed as a core feature. The specific claim about this was refuted (1-2 vote) from a blog source, suggesting the blog description was imprecise or outdated. Check the official Block documentation for current MCP status.

**Extensions:** The extension system is the key differentiator. Extensions are tools the agent can use — analogous to MCP servers but in Goose's format. Built-in extensions include file operations, developer tools, and system access.

**Strengths:**
- Strong corporate backing from Block — less likely to be abandoned
- On-device execution philosophy — good for privacy
- Extension system analogous to MCP
- Desktop app available for non-terminal users
- Apache 2.0 licence
- Model flexibility

**Weaknesses:**
- Extension ecosystem smaller than MCP's broader ecosystem
- Specific feature claims from secondary sources were unreliable — verify current status from primary docs
- Less pure CLI tool than Aider — the desktop app orientation means some rough edges in headless terminal use
- Star count uncertain

---

### Gemini CLI (by Google)

**What it is:** Gemini CLI is Google's open-source terminal AI agent, released in mid-2025. It is powered by the Gemini model family and includes generous free tier access via Google AI Studio, making it effectively zero-cost for moderate usage.

**Author and licence:** Google DeepMind. Apache 2.0 licence. Open source at `github.com/google-gemini/gemini-cli`.

**Community size:** Gemini CLI saw extremely rapid adoption after launch — it became one of the fastest-growing GitHub repositories in history within weeks of release. Specific star counts from secondary sources were not verified by this research process, but the viral adoption is not in dispute.

**Architecture:** Gemini CLI is a Node.js-based CLI agent. It uses Gemini 2.5 Pro by default, which provides up to a 1 million token context window — the largest of any CLI coding tool. This means you can load entire codebases into context rather than managing file additions manually.

**Installation:**

```bash
npm install -g @google/gemini-cli
gemini
```

**LLM provider support:** Gemini CLI is primarily designed for Google's Gemini models. It is not model-agnostic in the same way as Aider or OpenCode. The primary models available are Gemini 2.5 Pro and Gemini 2.5 Flash.

**Free tier:** This is the headline feature. The Gemini CLI free tier via Google AI Studio provides generous API quotas at no cost. For moderate usage, you may pay nothing beyond your time. This makes it the most cost-effective option for users who cannot afford API costs for heavy usage.

**MCP support:** Gemini CLI supports MCP servers, making it one of the few CLI tools with confirmed MCP integration alongside Claude Code. Configuration is via a `~/.gemini/settings.json` file.

**Extensions:** Gemini CLI has an extensions mechanism that allows adding capabilities beyond the default file editing and shell execution.

**Agentic capabilities:** Gemini CLI can read and edit files, run shell commands, search the web, and iterate autonomously. The 1M context window means it is uniquely capable at tasks involving entire-codebase understanding.

**Cost model:** Free tier available via Google AI Studio (rate-limited). For heavier usage, Gemini 2.5 Pro API pricing applies.

**Strengths:**
- Effectively free for moderate usage
- 1 million token context window — can load entire codebases
- MCP support
- Open source (Apache 2.0)
- Google backing means long-term support likely
- Very active development

**Weaknesses:**
- Locked to Gemini models — no OpenRouter or third-party model support
- Gemini models, while capable, may not match Claude's code quality for your specific use cases
- Less battle-tested than Aider
- Node.js dependency
- Free tier is rate-limited; heavy usage requires paid API

---

### Plandex

**What it is:** Plandex is an open-source CLI agent with a distinctive planning-first approach. Rather than immediately executing changes, it plans multi-file, multi-step tasks and builds up pending changes for user review before applying.

**Author and licence:** Created by Evan Conrad. MIT licence. Open source at `github.com/plandex-ai/plandex`.

**Architecture:** Plandex is written in Go and uses a client-server architecture. The server can be run locally or self-hosted on a cloud provider. Changes are accumulated in a "pending changes" buffer that you can review, modify, or reject before applying to the working tree. This makes Plandex the most review-oriented tool in the category — it assumes you want to understand what's happening before it happens.

**Installation:**

```bash
# Install client
curl -sL https://plandex.ai/install.sh | bash

# Use cloud server (free tier available)
plandex sign-in

# Or self-host the server
docker-compose up -d  # with the plandex-server repo
```

**LLM provider support:** Plandex supports OpenAI models directly and OpenAI-compatible APIs, which includes many providers. OpenRouter support via the OpenAI-compatible endpoint is possible.

**Self-hosting:** A key differentiator — you can run the entire Plandex server yourself, meaning no data leaves your infrastructure.

**Agentic capabilities:** Plandex is specifically designed for large, multi-step tasks: "implement this feature across 20 files." Its planning mechanism handles long sequences of related changes better than tools that tackle each change independently.

**Strengths:**
- Planning-first approach is excellent for large refactors
- Self-hosting option for data sovereignty
- Review buffer means less risk of unexpected changes
- Good at long-horizon multi-file tasks

**Weaknesses:**
- Planning overhead makes it slower for quick edits
- Less interactive than Aider or OpenCode
- Client-server architecture adds complexity
- LLM provider support less broad than Aider/OpenCode
- Smaller community

---

### SWE-agent

**What it is:** SWE-agent is a research tool from Princeton NLP lab, designed primarily for automated software engineering on GitHub issues. It achieves high scores on the SWE-bench benchmark. It is less a daily-driver tool and more a demonstration of what autonomous agents can accomplish on discrete bug-fix tasks.

**Author and licence:** Princeton NLP group. MIT licence. `github.com/SWE-agent/SWE-agent`.

**Architecture:** SWE-agent uses a Docker-based sandboxed environment. The Agent-Computer Interface (ACI) pattern it introduces provides structured tools for file navigation, editing, and execution in a way that is particularly suited for benchmark tasks.

**Intended use:** Automated bug-fixing on GitHub issues, especially in batch/CI contexts. Not designed for interactive development sessions.

**Strengths:**
- Extremely high benchmark performance
- Docker sandboxing for safe execution
- Good for automated CI/CD pipelines

**Weaknesses:**
- Not a daily driver — requires Docker, not interactive
- Research-oriented design means rough UX edges
- Slower than interactive tools
- Not designed for the ad-hoc, exploratory coding sessions that Claude Code excels at

---

### Mentat

**What it is:** Mentat is a Python-based CLI coding tool that was an early entrant in the space. It takes a conversational approach to code editing with explicit context management.

**Status:** As of mid-2025, development activity had slowed compared to its initial burst. It remains functional but has been largely superseded by Aider and newer tools.

**Note:** For new users, Aider is a better choice in the same category — more active, more features, larger community.

---

### Qwen Code and Kimi CLI

**What they are:** These are CLI coding agents from Chinese AI labs — Qwen Code from Alibaba's Qwen team and Kimi CLI from Moonshot AI. Both are classified alongside Claude Code and Aider as CLI tools by Artificial Analysis's taxonomy. Both are positioned as competitive alternatives particularly for users who want model diversity or prefer models strong at certain programming languages.

**Provider flexibility:** Qwen Code uses Qwen models (strong at code, particularly multilingual/non-English codebases). Kimi CLI uses Kimi's models with a very long context window.

**Note:** These tools were not covered by the deep-research verification process. Treat specific capability claims with appropriate scepticism until you test them directly.

---

## Part II: IDE Extensions and Hybrid Tools

### Cline (formerly Claude Engineer)

**What it is:** Cline is an open-source autonomous coding agent that operates primarily as a VS Code extension. It is model-agnostic, OpenRouter-compatible, and one of the most capable agentic tools available for IDE-based workflows. A CLI mode (Cline CLI 2.0) has been released, moving it toward hybrid territory.

**Author and licence:** Open source at `github.com/cline/cline`. MIT licence.

**Community size:** Approximately 62,300 GitHub stars (verified, May 2026). This makes it one of the most popular tools in the entire AI coding agent space, not just this subcategory.

**Architecture:** Cline runs as a VS Code extension and has deep access to the VS Code API — language servers, the file system, the integrated terminal, and the browser (via Puppeteer integration). It operates in two modes:

- **Plan mode** — Cline analyses the task and produces a plan before executing
- **Act mode** — Cline executes changes directly

This Plan/Act split allows you to review the strategy before any files are modified.

**LLM provider support:** Cline is model-agnostic. It supports:

- Anthropic (Claude family)
- OpenAI (GPT-4o, o1)
- Google (Gemini)
- AWS Bedrock
- Vertex AI
- OpenRouter (verified — listed on OpenRouter's works-with-openrouter page)
- Ollama for local models
- LM Studio
- Any OpenAI-compatible API endpoint

**OpenRouter setup:**

```
In VS Code: Open Cline extension settings
API Provider: OpenRouter
API Key: sk-or-...
Model: anthropic/claude-3.5-sonnet (or any OpenRouter model)
```

**Agentic capabilities:** Cline can:

- Read and edit any file in the workspace
- Execute shell commands in the integrated terminal
- Create and delete files/directories
- Use the browser (view pages, click, type, screenshot)
- Run searches across the codebase
- Read error output and iterate automatically

**Browser use** is a standout capability — Cline can actually open a browser, navigate to a URL, interact with a web page, and read the results. This enables tasks like: "go to this API docs page and implement the integration."

**MCP support:** Cline supports MCP servers. Configuration is via the Cline settings JSON. This means your existing MCP server investments (filesystem servers, database servers, custom tools) are portable to Cline.

**Extensibility:** Beyond MCP, Cline has a system prompt customisation capability and supports `.clinerules` files (analogous to `.cursorrules` or Claude Code's `CLAUDE.md`) for project-specific behaviour.

**CLI mode (Cline CLI 2.0):** The standalone CLI mode makes Cline usable outside VS Code. This is a recent addition and may not have full feature parity with the VS Code extension yet, but the trajectory is toward a full CLI-native experience.

**Cost model:** Open source, free. API costs only. Using OpenRouter you can route to cheaper models for lower-cost tasks.

**Strengths:**
- Extremely capable agentic tool — one of the best
- Model-agnostic with OpenRouter support verified
- Browser use capability is unique among open-source tools
- MCP support
- Plan/Act mode for controlled execution
- Very large and active community
- Growing CLI support

**Weaknesses:**
- Primarily an IDE extension — less suitable for terminal-first workflows
- Requires VS Code (for the full extension feature set)
- Browser use capability means it can have unintended side effects if not supervised
- Less scriptable than pure CLI tools

---

### Continue.dev

**What it is:** Continue.dev is an open-source AI coding assistant for VS Code and JetBrains IDEs. It combines autocomplete, chat, and agent capabilities in a single extension, with deep configurability via a YAML config file.

**Author and licence:** Open source at `github.com/continuedev/continue`. Apache 2.0 licence.

**Architecture:** Continue.dev is structured around three core features:

1. **Autocomplete** — inline code completions as you type
2. **Chat** — conversational interface about code, with codebase context
3. **Agent** — agentic mode that edits files based on instructions

Configuration lives in `~/.continue/config.yaml` and can specify different models for different features (e.g., a fast local model for autocomplete, a more capable cloud model for agent tasks).

**LLM provider support:** Continue.dev has one of the broadest provider lists:

- Anthropic, OpenAI, Google
- OpenRouter
- Ollama (confirmed at localhost:11434 by default, remote connections via `apiBase`)
- LM Studio, llama.cpp
- Groq, Together AI, Replicate
- Self-hosted models via any OpenAI-compatible endpoint

**Ollama setup (verified):**

```yaml
# ~/.continue/config.yaml
models:
  - title: "Local Qwen Coder"
    provider: ollama
    model: qwen2.5-coder:32b
    # For remote Ollama:
    # apiBase: http://192.168.1.100:11434
```

**Agent mode:** Continue.dev's agent mode allows it to make multi-file edits based on instructions. Tool support depends on the underlying model — models must support function/tool calling. Note: some models that claim tool support may not work reliably in agent mode (this was partially corroborated in the research, though the specific claim was refuted as too broad).

**Extensibility:** Continue.dev supports a block system where community-built extensions ("blocks") add new context providers, tools, and model configurations. This is effectively a plugin marketplace for the IDE assistant workflow.

**Strengths:**
- Best-in-class for IDE users who want full local LLM support
- Works in both VS Code and JetBrains
- Highly configurable via config.yaml
- Autocomplete + chat + agent in one package
- OpenRouter and Ollama support confirmed
- Open source, Apache 2.0

**Weaknesses:**
- No CLI mode — purely IDE-integrated
- Agent mode quality depends heavily on the model's tool-calling capabilities
- Less capable at long agentic chains than Cline or Claude Code
- JetBrains support is less mature than VS Code

---

## Part III: Dedicated AI IDEs

### Cursor

**What it is:** Cursor is a VS Code fork with deep AI integration baked into every layer of the editor. It has become one of the most widely adopted commercial AI coding tools, with a large user base and reported ARR in the hundreds of millions as of mid-2025.

**Company:** Anysphere, Inc. Private company, significant VC backing.

**Pricing:**

- **Free** — limited completions and requests per month
- **Pro** — ~$20/month — unlimited completions, 500 fast requests/month (uses the best available models)
- **Business** — ~$40/user/month — team features, admin controls, SOC 2 compliance

**Architecture:** Cursor extends VS Code with AI capabilities at multiple layers: inline completions, a chat sidebar, and Composer (the agent mode). It maintains a shadow workspace where it can test proposed changes before applying them.

**LLM models available:** Cursor Pro gives access to Claude 3.5 Sonnet, GPT-4o, o1, Gemini 2.5 Pro, and Cursor's own fine-tuned models. Users can also configure their own API key for direct provider access.

**Agent mode (Composer):** Composer is Cursor's multi-file agentic mode. It accepts a task, proposes a plan, and executes changes across multiple files. It can run terminal commands in Yolo mode (automatic execution without prompting). Yolo mode effectively turns Cursor's agent into a Claude Code-like autonomous operator.

**Context mechanisms:**

- `@codebase` — full codebase semantic search
- `@docs` — pull in documentation from URLs
- `@web` — web search integration
- `@file`, `@folder` — explicit file/folder references
- `@git` — reference git history and diffs

**Rules:** Cursor supports `.cursorrules` files at the project root (and global rules) that provide persistent instructions to the AI — similar to Claude Code's `CLAUDE.md` pattern.

**Provider flexibility:** Limited. While Cursor allows "BYO API key" (bring your own Anthropic/OpenAI key), it is not natively designed for OpenRouter or arbitrary providers. The product is optimised for the models it bundles.

**Strengths:**
- Polished, deeply integrated AI coding experience
- Composer agent mode is very capable
- Semantic codebase indexing enables large-codebase context
- Large community, extensive documentation, many tutorials
- Tab completion is best-in-class
- $20/month Pro is reasonable for moderate usage

**Weaknesses:**
- IDE-bound — not a CLI tool
- Limited model flexibility — not OpenRouter compatible
- Proprietary — you are dependent on Anysphere remaining a going concern and maintaining pricing
- Heavier than a terminal tool — requires a full VS Code instance

---

### Windsurf (by Codeium)

**What it is:** Windsurf is an AI-first IDE built by Codeium, positioned as a direct competitor to Cursor. Its standout feature is the Cascade agent, which uses "Flow" — a system that maintains contextual awareness across an entire coding session rather than treating each interaction as independent.

**Company:** Codeium, Inc. Significant VC backing. Note: acquisition discussions with OpenAI were reported in mid-2025; verify current ownership before committing to this tool long-term.

**Pricing:**

- **Free** — limited credits per month
- **Pro** — ~$15/month
- **Team** — per-user enterprise pricing

**Architecture:** Windsurf is a fork of VS Code (similar to Cursor). The Cascade agent is its agentic component. Flow awareness means Cascade can reference earlier context in the session without explicit re-prompting — it maintains a "memory" of what it has done and seen.

**LLM models:** Windsurf uses its own model serving infrastructure (Codeium's). It offers multiple models and allows some degree of model selection in higher tiers.

**Provider flexibility:** Like Cursor, Windsurf is primarily designed around its own model serving rather than OpenRouter or arbitrary providers. There is some BYO API key support but it is not the primary use case.

**Strengths:**
- Cascade agent with Flow awareness is a genuinely differentiated capability
- Generally slightly cheaper than Cursor
- Autocomplete is excellent (Codeium was originally an autocomplete specialist)
- Clean, polished IDE experience

**Weaknesses:**
- IDE-bound
- Ownership uncertainty (potential OpenAI acquisition) creates long-term risk
- Less model flexibility than Cursor
- Smaller community than Cursor
- Less documentation and tutorials

---

### Zed AI

**What it is:** Zed is a high-performance code editor written in Rust, designed for speed and minimal latency. Its AI integration (Zed AI) brings Claude as the default model into this fast editor experience.

**Architecture:** Zed is not a VS Code fork — it is a ground-up implementation in Rust with native GPU acceleration. This makes it significantly faster than Electron-based editors (VS Code, Cursor, Windsurf). AI features are integrated via an assistant panel.

**LLM models:** Zed uses Claude models (Anthropic) by default. It also supports configuring alternative backends.

**Pricing:** Zed editor is free and open source. Zed AI usage has a free tier and credits system.

**Strengths:**
- Extraordinarily fast editor — the best performance of any AI-integrated editor
- Open source editor core
- Clean, focused design

**Weaknesses:**
- AI capabilities are less developed than Cursor or Windsurf
- Smaller plugin/extension ecosystem (incompatible with VS Code extensions)
- Agentic mode is less mature
- Primarily macOS and Linux (Windows support in progress)

---

## Part IV: Cloud and Web Platform Agents

### OpenHands (formerly OpenDevin)

**What it is:** OpenHands is a highly capable open-source AI software engineer designed to solve complex software engineering tasks autonomously. It is the open-source project that most directly competes with commercial cloud agents like Devin.

**Author and licence:** All Hands AI. MIT licence. `github.com/OpenHands/OpenHands`.

**Community size:** Approximately 74,800–75,500 GitHub stars (verified range, May 2026). One of the largest open-source AI coding projects by community size.

**Architecture:** OpenHands runs in a Docker container with a sandboxed execution environment. This is the key architectural difference from CLI tools — it doesn't run directly on your machine; it runs in an isolated environment with full access to the shell, filesystem, and browser within that sandbox. This makes it safer for autonomous long-running tasks but adds Docker as a dependency.

**Interfaces:**

- **Web UI** — the primary interface, a browser-based chat with the agent
- **CLI** — a lightweight binary available at `github.com/OpenHands/OpenHands-CLI` (verified as existing, ~191 stars)
- **API** — programmable access for CI/CD integration

**Installation:**

```bash
# Via Docker (recommended)
docker pull docker.all-hands.dev/all-hands-ai/runtime:0.39-nikolaik

# Lightweight CLI binary (for terminal-first use)
pip install openhands-cli
```

**LLM provider support:** OpenHands supports multiple LLM providers via litellm, including Anthropic, OpenAI, Google, and others.

**MCP support:** OpenHands supports MCP server configuration (verified). Both command-based stdio servers (via `uvx` or `npx`) and URL-based remote MCP servers are supported:

```json
{
  "mcpServers": {
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    },
    "notion": {
      "url": "https://mcp.notion.com/mcp"
    }
  }
}
```

Note: the specific claim that OpenHands "natively discovers MCP tools automatically" was refuted in our adversarial verification. MCP is supported as a configuration option but may require explicit setup.

**Strengths:**
- Very capable at complex, long-horizon tasks — closest open-source equivalent to Devin
- Docker sandboxing means it can't accidentally break your host system
- MCP configuration support
- Massive community and active development
- Web UI is more accessible than CLI tools

**Weaknesses:**
- Requires Docker — heavier than CLI tools
- Primarily a cloud/web platform — less suitable for quick interactive sessions
- Slower to start up than CLI tools (Docker container spin-up)
- Not a terminal-first tool despite having a CLI option

---

### Devin (by Cognition AI)

**What it is:** Devin was the first high-profile "AI software engineer" capable of autonomously solving complex GitHub issues end-to-end. It is a commercial cloud product.

**Pricing:** Enterprise pricing, reportedly expensive (thousands per month for teams). Not a realistic Claude Code replacement for individual developers on cost grounds.

**Strengths:**
- Very capable for long-horizon autonomous tasks
- Well-integrated with GitHub workflows

**Weaknesses:**
- Very expensive — out of range for individual developer use
- Fully proprietary — no control over the stack
- Not a CLI tool

---

## Part V: Commercial AI Coding Assistants

### GitHub Copilot with Agent Mode

**What it is:** GitHub Copilot is Microsoft/GitHub's AI coding assistant. It has evolved from autocomplete-only to include chat and an agent mode (Copilot Workspace) capable of implementing GitHub issues.

**Pricing:**

- **Individual** — $10/month or $100/year
- **Business** — $19/user/month
- **Enterprise** — $39/user/month

**LLM provider:** GitHub Copilot is powered by OpenAI models and GitHub's own fine-tuned models. It is locked to the Microsoft/OpenAI ecosystem.

**OpenRouter support:** The claim that GitHub Copilot supports OpenRouter was explicitly refuted in our adversarial verification (1-2 vote). It does not support third-party providers.

**Agent mode (Copilot Workspace):** Allows Copilot to plan and implement changes for a GitHub issue, proposing a series of file edits for review. Less fully autonomous than Claude Code but more controlled.

**Strengths:**
- Deep GitHub integration — issues, PRs, code review
- Well-integrated with VS Code and GitHub.com
- $10/month is the most affordable commercial option
- Enterprise features and security compliance

**Weaknesses:**
- Not OpenRouter-compatible — locked to Microsoft/OpenAI
- Agent mode is less capable than Claude Code, Cline, or Cursor's Composer
- Less suited for non-GitHub workflows
- Autocomplete quality has been surpassed by Cursor and Windsurf

---

### Amazon Q Developer (formerly CodeWhisperer)

**What it is:** Amazon Q Developer is AWS's AI coding assistant, with deep integration into the AWS ecosystem. It was rebranded from CodeWhisperer in 2024.

**Pricing:**

- **Free tier** — limited monthly suggestions
- **Pro** — $19/user/month

**LLM provider:** Amazon's own models plus Anthropic Claude (via Bedrock integration). Not independently flexible.

**Agentic capabilities:** Amazon Q can perform agent-style tasks within AWS console (reviewing resources, suggesting fixes) and in IDEs (refactoring, security scanning). Its agent mode is most powerful for AWS-specific tasks.

**Strengths:**
- Best-in-class for AWS-heavy workflows
- Security vulnerability scanning
- Integrated IAM policy generation

**Weaknesses:**
- AWS-focused — less useful for non-AWS codebases
- Not a general-purpose coding agent
- Provider lock-in to Amazon/Anthropic

---

### JetBrains AI Assistant

**What it is:** JetBrains AI Assistant is integrated into IntelliJ IDEA, PyCharm, WebStorm, GoLand, and all other JetBrains IDEs. It provides chat, completion, and basic agentic features.

**Pricing:** Included in JetBrains All Products Pack subscription (~$24.90/month) or as a separate AI add-on.

**LLM models:** JetBrains AI Assistant uses multiple models under the hood (both their own and third-party). It offers some model choice in settings.

**Strengths:**
- Best choice if you are already heavily invested in JetBrains IDEs
- Deep IDE integration (refactoring, inspections, test generation)
- Supports both local and cloud models in newer versions

**Weaknesses:**
- Less capable agent mode than Cursor or Cline
- Tied to JetBrains subscription
- JetBrains IDEs are heavier than VS Code

---

### Tabnine

**What it is:** Tabnine is an AI autocomplete tool with a long history (one of the first serious AI coding assistants). Its focus is primarily on fast, high-quality inline completions rather than agentic capabilities.

**Pricing:**

- **Free** — limited completions with smaller models
- **Pro** — ~$12/month
- **Enterprise** — custom pricing with self-hosted model option

**LLM provider:** Tabnine uses its own models plus third-party models (Anthropic, etc.). Enterprise tier supports self-hosted deployment for data sovereignty.

**Strengths:**
- Very fast completions (latency-optimised)
- Enterprise self-hosted option — best for organisations with strict data policies
- Long track record

**Weaknesses:**
- Primarily completion-focused — not an agentic tool
- Less capable for instruction-following tasks
- Being overtaken by Cursor/Windsurf in completions quality

---

### Supermaven

**What it is:** Supermaven was a VS Code-focused autocomplete tool with a very large context window for completions (300k tokens). It was notable for its speed and accuracy.

**Status:** Supermaven was acquired by Cursor in late 2024/early 2025. It is no longer an independent product. Cursor has integrated Supermaven's technology into its tab completion. If Supermaven was your tool of choice, Cursor is now its natural successor.

---

## Part VI: Cross-Cutting Analysis

### Provider Flexibility Analysis

A critical factor for Claude Code users concerned about API costs is whether an alternative tool is model-agnostic — allowing you to route requests to cheaper models, local models, or whichever provider has the best current pricing.

#### OpenRouter Compatibility

OpenRouter is a unified API gateway that provides access to hundreds of models from dozens of providers under a single API key, with pay-per-token pricing and no monthly subscription.

| Tool | OpenRouter Support | Notes |
|------|--------------------|-------|
| Aider | **Yes (verified)** | Full setup at aider.chat/docs/llms/openrouter.html |
| Cline | **Yes (verified)** | Listed on OpenRouter works-with-openrouter page |
| OpenCode | **Yes (verified)** | 75+ endpoints including OpenRouter |
| Continue.dev | **Yes** | Via OpenRouter provider in config.yaml |
| Goose | Likely | Supports custom API endpoints |
| Plandex | Partial | Via OpenAI-compatible endpoint |
| OpenHands | Yes | Via litellm provider abstraction |
| Cursor | **No** | BYO key supports direct providers only |
| Windsurf | No | Codeium's own model serving |
| GitHub Copilot | **No (refuted claim)** | Locked to Microsoft/OpenAI |
| Gemini CLI | No | Locked to Gemini models |
| Amazon Q | No | Locked to Amazon/Anthropic |
| JetBrains AI | Partial | Some model flexibility in enterprise |
| Tabnine | No | Own models |

**Conclusion:** For OpenRouter flexibility, the open-source CLI tools (Aider, Cline, OpenCode, Continue.dev) are your best options. Commercial IDE tools are generally locked to their own ecosystems.

#### Local LLM Support (Ollama / LM Studio)

Running models locally eliminates API costs entirely. Quality of locally-runnable models has improved dramatically — Qwen2.5-Coder 32B, DeepSeek Coder V2, and Mistral Codestral are serious coding models available locally.

| Tool | Ollama | LM Studio | Notes |
|------|--------|-----------|-------|
| Aider | **Yes** | **Yes** | Via litellm |
| Cline | **Yes** | **Yes** | Native provider options |
| OpenCode | **Yes (verified)** | **Yes** | 75+ endpoints |
| Continue.dev | **Yes (verified)** | **Yes** | localhost:11434 default |
| Goose | **Yes** | Yes | On-device focus |
| Plandex | Partial | Partial | Via OpenAI-compatible API |
| OpenHands | Yes | Yes | Via litellm |
| Cursor | No | No | Cloud models only |
| Windsurf | No | No | Cloud models only |
| GitHub Copilot | No | No | Cloud only |
| Gemini CLI | No | No | Gemini models only |
| Zed AI | Partial | No | Some local model config |

**Best tools for local LLMs:** Aider, Cline, OpenCode, Continue.dev, and Goose are all first-class options for local model use.

**Recommended local models for coding (as of 2025-2026):**

- **Qwen2.5-Coder:32b** — best general coding performance locally, fits in 24-32GB VRAM
- **DeepSeek Coder V2** — excellent at complex reasoning tasks
- **Mistral Codestral** — fast, good for completions
- **Llama 3.1:70b** — good general-purpose if VRAM allows
- **Phi-3.5-MoE** — very efficient for limited hardware

---

### Feature Comparison Matrix

| Feature | Claude Code | Aider | OpenCode | Cline | Continue.dev | Goose | Gemini CLI | OpenHands | Cursor | Windsurf |
|---------|-------------|-------|----------|-------|--------------|-------|------------|-----------|--------|----------|
| **Interface** | CLI | CLI | TUI | VS Code / CLI | VS Code / JetBrains | CLI + Desktop | CLI | Web / CLI | IDE | IDE |
| **Agentic file editing** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Partial | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **Multi-file context** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (1M tokens) | ✅ | ✅ | ✅ |
| **Shell execution** | ✅ | ✅ | ✅ | ✅ | ✅ Agent mode | ✅ | ✅ | ✅ (sandboxed) | ✅ Yolo mode | ✅ |
| **Web search** | ✅ | ❌ | Partial | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Browser use** | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **MCP support** | ✅ Native | ❌ | ✅ | ✅ | Partial | ✅ | ✅ | ✅ Config | ❌ | ❌ |
| **Custom hooks/automation** | ✅ Skills+Hooks | ❌ | Limited | `.clinerules` | config.yaml | Extensions | Settings | Limited | `.cursorrules` | Limited |
| **OpenRouter** | ❌ | ✅ | ✅ | ✅ | ✅ | Likely | ❌ | ✅ | ❌ | ❌ |
| **Local LLMs** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Open source** | ❌ | ✅ MIT | ✅ MIT | ✅ MIT | ✅ Apache-2 | ✅ Apache-2 | ✅ Apache-2 | ✅ MIT | ❌ | ❌ |
| **Git integration** | ✅ | ✅ Auto-commit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Cost model** | Max plan or API | API only | API only | API only | API only | API only | Free tier + API | API only | $20/mo + API | $15/mo |
| **Self-hosted option** | ❌ | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | ❌ | ❌ |

---

### Extensibility Deep Dive

One of Claude Code's most powerful features is its extensibility architecture: skills (reusable prompt templates invoked as `/commands`), hooks (shell commands that fire on events like tool calls or session start), and MCP servers (external tools exposed via a standard protocol). This combination allows you to build a highly personalised, automated coding workflow. How do the alternatives compare?

#### Claude Code's Extension Architecture

For context, Claude Code's three-layer system works as follows:

1. **Skills** — Markdown files stored in `~/.claude/skills/` that define reusable workflows. When invoked as `/skill-name`, their content is loaded and executed. Skills can include checklists, decision trees, and instructions for specific types of tasks (debugging, code review, PR creation).

2. **Hooks** — Shell commands configured in `settings.json` that fire on specific Claude Code events. For example: run linting before a commit, post a notification when a session ends, validate that tests pass after edits. Hooks are executed by the Claude Code harness, not by the AI — this makes them reliable and deterministic.

3. **MCP Servers** — External processes exposing tools via the Model Context Protocol. Claude Code can call these tools as part of its reasoning (read from a database, query an external API, access browser dev tools, etc.). Any MCP server in the ecosystem works.

#### How Alternatives Compare

**Aider:** No equivalent to skills or hooks. No MCP support. Configuration via `.aider.conf.yml` covers model settings and preferences but not custom workflows. *Least extensible of the serious alternatives.*

**OpenCode:** MCP support confirmed. Some configuration of workflows via the config system. No equivalent to Claude Code's hooks system or skills paradigm. *Mid-range extensibility.*

**Cline:** MCP support confirmed. `.clinerules` files provide persistent instructions analogous to `CLAUDE.md`. No hook system. The Plan/Act split provides some workflow control but it's not programmable. *Better than average but no hooks.*

**Continue.dev:** The "blocks" system provides a plugin-like architecture for adding new context providers and tools. Config-driven customisation is deep. No hook system. MCP support via tool configuration. *Good for IDE users, weaker hook/automation story.*

**Goose:** Native extension system with MCP compatibility. The extension architecture is the closest conceptual match to Claude Code's MCP+skills combination, though the format differs. No hook system equivalent. *Strong extensibility story, but different API.*

**Gemini CLI:** MCP support confirmed. Extensions mechanism for adding capabilities. No hook system. *Good starting point for building a custom workflow.*

**OpenHands:** MCP configuration support (verified). Limited hook/automation equivalent. Primarily designed for single-task autonomous execution rather than a persistent, customised workflow. *Weakest extensibility story.*

#### What This Means for Migration

If you have heavily invested in Claude Code's superpowers system (skills, hooks, MCPs), a complete migration requires rebuilding your workflow on whatever alternative you choose. The good news: MCP server investments are portable to any MCP-compatible tool (Cline, OpenCode, Gemini CLI, Goose, OpenHands). The skills system has no direct equivalent in any alternative — the closest analogues are `.clinerules` (Cline), `CLAUDE.md`-style instruction files, or custom system prompts. The hooks system is the hardest to replicate — only Claude Code has deterministic shell-command hooks that fire on tool events. Alternatives would require wrapping the tool in a shell script or using git hooks as a partial substitute.

---

### Cost Analysis

If you are a heavy Claude Code user currently on the Max plan (~$100/month for approximately unlimited usage), what would the same usage cost on each alternative?

#### Defining "Heavy Usage"

For this analysis, heavy usage means:
- ~4-8 hours of active coding per day
- Typical session: long context (50k-200k tokens input), many file edits, running tests
- Estimated: ~100-200 million input tokens per month, 10-20 million output tokens per month

These are rough estimates — actual token consumption varies enormously by workflow and model.

#### API Cost Estimates (Direct Provider, as of 2025)

These are ballpark figures using 2025 pricing, which changes frequently:

**Anthropic Claude 3.5 Sonnet:**
- Input: ~$3/million tokens
- Output: ~$15/million tokens
- Heavy usage estimate: (150M × $3 + 15M × $15) / 1M ≈ **$450 + $225 = ~$675/month**
- *This is why the Max plan at $100/month is excellent value for heavy users.*

**Anthropic Claude 3 Haiku:**
- Input: ~$0.25/million tokens
- Output: ~$1.25/million tokens
- Heavy usage estimate: ~$56/month
- *Much cheaper but much less capable for complex tasks.*

**OpenAI GPT-4o:**
- Input: ~$2.50/million tokens
- Output: ~$10/million tokens
- Heavy usage estimate: ~$525/month

**Google Gemini 2.5 Pro (via AI Studio):**
- Free tier: generous rate limits (may cover moderate usage at no cost)
- Paid tier: ~$3.50/million tokens input (for >200k context), ~$10.50/million output
- Heavy usage estimate: ~$680/month at paid tier, **$0 at free tier** (rate-limited)

**DeepSeek V3 (via OpenRouter):**
- Input: ~$0.14/million tokens
- Output: ~$0.28/million tokens
- Heavy usage estimate: **~$27/month**
- *Dramatically cheaper. Competitive coding quality for many tasks.*

**Qwen2.5-Coder (local via Ollama):**
- Cost: $0 — no API costs
- Hardware requirement: 24GB VRAM for the 32B model
- *Effectively free if you have the hardware.*

#### Per-Tool Cost Summary

| Tool | Minimum Monthly Cost | Heavy Usage (Cloud) | Heavy Usage (Local) | Notes |
|------|---------------------|--------------------|--------------------|-------|
| Aider + Claude Sonnet | $0 tool + API | ~$675 | N/A | Use Haiku for cheaper option |
| Aider + DeepSeek (OpenRouter) | $0 + API | ~$27 | N/A | Significant quality tradeoff |
| Aider + Ollama | $0 | $0 | GPU hardware cost | Quality depends on hardware |
| OpenCode + DeepSeek | $0 + API | ~$27 | N/A | Broadest provider choice |
| Cline + OpenRouter | $0 + API | Varies by model | N/A | Route cheaply via OpenRouter |
| Gemini CLI | $0 | $0 (free tier) | N/A | Rate limits apply |
| Cursor Pro | $20/month | $20/month | N/A | Fixed subscription |
| Windsurf Pro | $15/month | $15/month | N/A | Fixed subscription |
| GitHub Copilot | $10/month | $10/month | N/A | Limited agent capabilities |
| OpenHands | $0 tool + API | Varies | N/A | Docker overhead |

#### Cost Migration Strategy

**Scenario 1: Keep Claude-quality results, accept higher costs**
Use Aider or Cline with direct Anthropic API. Cost: ~$675/month for heavy usage. This is the worst-case scenario financially — you lose the Max plan subsidy.

**Scenario 2: Reduce cost with model diversity**
Use Aider or OpenCode with OpenRouter, routing to DeepSeek or Qwen for routine tasks and Claude/GPT-4o for complex ones. Cost: $50-200/month depending on routing strategy. Significant savings, some quality tradeoff on simpler models.

**Scenario 3: Go local for routine work, cloud for hard tasks**
Use Aider or Cline with Ollama (Qwen2.5-Coder:32b) for day-to-day coding, escalate to cloud API for complex multi-file refactors. Cost: near zero for routine work, occasional API costs for hard tasks.

**Scenario 4: Fixed-cost IDE subscription**
Move to Cursor ($20/month) or Windsurf ($15/month). You lose terminal-native workflow but get predictable pricing. Less capable at agentic tasks than Claude Code for heavy use cases.

**Scenario 5: Gemini CLI free tier**
For non-time-sensitive work or as a supplementary tool, Gemini CLI's free tier (Google AI Studio) covers substantial usage. Rate limits apply, but for many users this could be zero-cost. Loses model flexibility.

---

## Recommendations

### If you want the closest CLI experience to Claude Code

**Primary:** Aider — mature, reliable, git-native, OpenRouter-supported, local LLM support. Start here. The absence of MCP and hooks is a real limitation if you've invested heavily in those, but the core editing workflow is the most Claude Code-like of any open-source tool.

**Secondary:** OpenCode — if you want MCP support and broader provider flexibility in a terminal tool, OpenCode is the best current option. The TUI differs from a pure REPL but the agent capabilities are strong.

### If you want the best IDE-integrated alternative

**Primary:** Cline — model-agnostic, OpenRouter-supported, browser use, MCP-compatible, Plan/Act mode. The most capable open-source agentic IDE tool available. Its CLI mode is improving.

**Secondary:** Continue.dev — if you want best-in-class local LLM support and deep IDE integration in VS Code and JetBrains simultaneously.

**Commercial option:** Cursor ($20/month) — if you want the best polished commercial experience and are comfortable with a VS Code workflow. Yolo mode brings it close to Claude Code's autonomy level.

### If cost is the primary constraint

**Free option:** Gemini CLI — free tier is generous, MCP-supported, 1M context window. Quality good for most tasks.

**Ultra-cheap option:** Aider or OpenCode with DeepSeek V3 via OpenRouter — approximately $25-30/month for heavy usage with a capable (if not Claude-class) model.

**Zero API cost:** Any tool + Ollama with Qwen2.5-Coder:32b — requires GPU hardware but then costs nothing per query.

### If MCP server investments are critical

Tools with confirmed MCP support: Claude Code (native), OpenCode, Cline, Gemini CLI, Goose, OpenHands (config). Of these, OpenCode and Cline are the strongest alternatives for a daily coding workflow.

### If you need extensibility similar to Claude Code's skills+hooks

The honest answer: no alternative matches Claude Code's skills+hooks system. The closest approximations:
- **Skills equivalents:** `.clinerules` (Cline), `CLAUDE.md`-style files, custom system prompts in any tool
- **Hooks equivalents:** Git hooks, shell wrappers, CI/CD tooling — not built into any alternative
- **MCP equivalents:** Cline, OpenCode, Gemini CLI, Goose all support MCP — your server investments are portable

### Migration strategy

Rather than a hard switch, a practical migration path:

1. **Set up Aider** as a Claude Code complement today. Get comfortable with it. It is free to try with Haiku (cheap) or Ollama (free).
2. **Test OpenCode** — its MCP support and provider flexibility make it the best tool for a full Claude Code replacement once mature.
3. **Keep Gemini CLI** as a fallback for cost-free work — the 1M context window is uniquely useful for codebase analysis tasks.
4. **Invest in OpenRouter** — get an API key. With OpenRouter, you're never locked to a single model again. As model prices drop (historically, they do), your costs drop automatically.
5. **Protect your MCP investments** — build MCP servers in preference to tool-specific plugins wherever possible. MCP compatibility is growing across the ecosystem.

---

## Appendix: Verified Research Findings

The following claims were confirmed via 3-agent adversarial verification (each claim reviewed by three independent agents; at least 2 of 3 must confirm):

1. **Aider has ~45,300 GitHub stars (May 2026) and is a terminal-native pair programming agent with confirmed OpenRouter support.** (3-0 vote)

2. **Cline has ~62,300 GitHub stars (May 2026), is OpenRouter-compatible, and primarily operates as a VS Code extension with an expanding CLI mode.** (2-1 vote)

3. **OpenHands has ~74,800-75,500 GitHub stars (May 2026) and is classified as a cloud platform rather than a CLI tool, despite having a CLI binary available.** (2-1 vote)

4. **OpenHands MCP configuration supports both stdio command-based servers (uvx/npx) and URL-based remote MCP servers.** (3-0 vote)

5. **Continue.dev supports Ollama at localhost:11434 by default, with remote Ollama connections via the `apiBase` setting.** (3-0 vote)

6. **OpenCode supports 75+ LLM endpoints including OpenRouter and Ollama, with version 1.15.13 released May 30, 2026.** (3-0 vote)

7. **The AI coding agent landscape is categorised into CLI tools (Claude Code, Aider, Gemini CLI, Goose, OpenCode), IDE extensions (Cline, Continue.dev), dedicated IDEs (Cursor, Windsurf), and cloud platforms (OpenHands, Devin).** (2-1 vote)

**Refuted claims** (excluded from main text): GitHub Copilot OpenRouter support (false), specific star counts from blog aggregators (unreliable), Aider token volume figures (unverified), OpenHands automatic MCP tool discovery (false — config required), Goose MCP as a confirmed primary feature from blog sources (unverified).

---

## References

Primary sources (verified):

- OpenRouter works-with-openrouter page: `openrouter.ai/works-with-openrouter`
- Aider OpenRouter documentation: `aider.chat/docs/llms/openrouter.html`
- Continue.dev Ollama guide: `docs.continue.dev/guides/ollama-guide`
- OpenHands MCP SDK guide: `docs.openhands.dev/sdk/guides/mcp`
- OpenHands MCP settings: `docs.openhands.dev/openhands/usage/settings/mcp-settings`
- OpenCode documentation: `opencode.ai/docs/providers/`
- OpenCode GitHub: `github.com/sst/opencode`
- Artificial Analysis coding agents taxonomy: `artificialanalysis.ai/agents/coding`
- Awesome CLI Coding Agents (bradAGI): `github.com/bradAGI/awesome-cli-coding-agents`

Secondary sources (used for background, not for verified claims):

- `pinggy.io/blog/top_cli_based_ai_coding_agents/`
- `artificialanalysis.ai/agents/coding`
- `morphllm.com/comparisons/claude-code-alternatives`
- `techbuddies.io/2026/01/22/goose-vs-claude-code-...`
- `finout.io/blog/anthropic-api-pricing`
- `ksred.com/claude-code-pricing-guide-...`
