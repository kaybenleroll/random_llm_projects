# Codex Model Comparison

_Checked 27 August 2026_

This briefing summarises the models discussed in relation to Codex and the OpenAI API: what they are good at, where they tend to be weaker, and how their costs compare. It does not assume that every model listed is enabled in every Codex account or interface.

## Short version

- **GPT-5.6 Sol** is the strongest general-purpose choice for difficult, ambiguous, or high-value work.
- **GPT-5.6 Terra** is the best everyday balance of quality, speed, and cost.
- **GPT-5.6 Luna** is the economical choice for straightforward or high-volume work.
- **GPT-5.5** remains highly capable, but is now an older frontier model.
- **GPT-5.3-Codex** is a coding specialist for agentic repository work.
- **Codex Spark** is intended for very fast, narrowly scoped iteration, especially UI changes.

### Availability note

GPT-5.6 Sol and GPT-5.5 have been used by subagents in this session, so their availability here is confirmed. The official documentation confirms GPT-5.6 Sol, Terra, Luna, GPT-5.5, and GPT-5.3-Codex as OpenAI API models; that does not by itself prove that each one appears in a particular Codex model picker. Codex Spark is documented as a Codex use case, but OpenAI does not currently publish a separate model specification or API price for it. Check the model picker and account usage display for the definitive list available to you.

## The GPT-5.6 family

OpenAI currently positions the GPT-5.6 models as a three-level family. Sol is the flagship model, Terra balances intelligence and cost, and Luna is optimized for cost-sensitive, high-volume workloads. All three have a 1.05-million-token context window and a maximum output of 128K tokens.

| Model | Strengths | Weaknesses and trade-offs | API price per 1M tokens |
|---|---|---|---:|
| **GPT-5.6 Sol** | Complex reasoning, research, difficult debugging, multi-file changes, nuanced writing, architecture, security-sensitive work | Most expensive; high reasoning settings can increase latency and usage | $4 input / $20 output |
| **GPT-5.6 Terra** | General coding, document work, debugging, analysis, and ordinary agent tasks | Less reliable than Sol on unusually ambiguous or difficult work | $2 input / $12 output |
| **GPT-5.6 Luna** | Extraction, formatting, simple transformations, routine code, and high-volume processing | More likely to miss subtle constraints or need correction on complex autonomous work | $0.20 input / $1.20 output |

The cached-input prices are $0.40 for Sol, $0.20 for Terra, and $0.02 for Luna per million tokens.

Relative to Luna, Terra costs approximately 10 times as much per token, while Sol costs 20 times as much for input and about 17 times as much for output. That difference matters most in long-running agent sessions, where context and tool results are repeatedly processed.

### GPT-5.6 Sol

Sol is the default choice when the cost of being wrong is significant or when the task requires judgment rather than simple execution. Good examples include:

- designing or reviewing a multi-file change;
- debugging a difficult or poorly understood failure;
- researching and synthesising several sources;
- restructuring a long document;
- reviewing another model’s work;
- security-sensitive or otherwise high-impact analysis.

Its main disadvantage is economic. It is not usually worth using for a mechanical formatting pass, a simple extraction task, or a well-specified one-file change. It also becomes slower and more expensive when used with high or maximum reasoning effort.

### GPT-5.6 Terra

Terra is the sensible default for most repository and document work. It should be capable of handling ordinary implementation, debugging, source edits, structured analysis, and moderate research while costing substantially less than Sol.

Its limitation is mostly one of margin. When a task has hidden requirements, many interacting files, uncertain architecture, or expensive failure modes, Sol is more likely to maintain the full problem structure and catch edge cases. Terra is the model I would normally start with, then escalate if the task exposes a genuine reasoning problem rather than a context or tooling problem.

### GPT-5.6 Luna

Luna is best viewed as a high-throughput workhorse. It is useful for:

- reformatting or normalising text;
- extracting fields from many documents;
- applying a clearly specified mechanical transformation;
- generating routine test cases or boilerplate;
- classifying or sorting material;
- making a first pass over a large volume of low-risk work.

Its weakness is subtlety. It is less appropriate when the task depends on interpreting ambiguous requirements, preserving many cross-file invariants, making careful editorial judgments, or working independently for a long time without review.

## GPT-5.5

GPT-5.5 is still a strong frontier model for coding, tool-heavy agents, long-context retrieval, grounded assistants, and professional work. It was used for one of the editorial subagent passes on the comparative religion document.

It remains useful when:

- an existing workflow has already been tuned for it;
- continuity with previous work matters;
- results need to be compared with earlier GPT-5.5 runs;
- a mature, capable general model is preferred for a particular task.

For new work, GPT-5.6 Sol is generally the better high-quality choice: the current family is newer, Sol is cheaper than GPT-5.5, and GPT-5.6 supports additional reasoning controls. GPT-5.5 costs $5 per million input tokens and $30 per million output tokens, with cached input at $0.50 per million.

## GPT-5.3-Codex

GPT-5.3-Codex is specialised for agentic coding in Codex-like environments. It is a good option for repository navigation, implementation loops, debugging, and code changes where coding ability matters more than broad research or prose quality.

Its strengths are coding focus, tool use, and a lower price than the frontier general models. Its context window is 400K tokens—substantially smaller than the GPT-5.6 family’s 1.05 million—and it is not the first choice for nuanced editorial work, comparative research, or broad conceptual analysis.

API pricing is $1.75 per million input tokens and $14 per million output tokens, with cached input at $0.175 per million.

It may still be cheaper overall than a cheaper general model if its coding specialisation means fewer repair cycles are needed.

## Codex Spark

Codex Spark is positioned as a very fast option for narrowly scoped iteration. The official Codex use-case material specifically presents it for fast, focused UI changes.

Good uses include:

- adjusting colours, spacing, typography, or layout;
- trying several small visual variants;
- making a clearly specified change to an existing interface;
- keeping an implementation loop moving when each step is easy to inspect.

It is a poor fit for large refactors, ambiguous requirements, architecture, difficult debugging, research synthesis, or work where a plausible but subtly wrong answer would be costly.

OpenAI’s public documentation does not currently provide a separate, reliable per-token price for Spark. Its effective cost is likely to appear through Codex plan usage or task quotas rather than ordinary API billing.

## Reasoning effort is a separate control

Model choice is only part of the decision. GPT-5.6 models support reasoning settings from `none` through `max`; GPT-5.5 supports up to `xhigh`; GPT-5.3-Codex supports up to `xhigh`.

Higher reasoning settings can improve difficult-task reliability, but they also increase latency and usage. A reasonable pattern is:

- `none` or `low` for simple, latency-sensitive work;
- `medium` as the ordinary starting point;
- `high` or `xhigh` for difficult work where extra reasoning helps;
- `max` on GPT-5.6 only when quality matters more than speed and cost.

A stronger model cannot compensate for missing context, unclear acceptance criteria, bad tool configuration, or insufficient verification.

## Recommended choices for our work

| Task | Recommended model |
|---|---|
| Simple text transformation or formatting | Luna |
| Small, well-specified source edit | Terra |
| Normal multi-file repository work | Terra, medium or high reasoning |
| Difficult debugging or architectural change | Sol, high or xhigh reasoning |
| Major research synthesis or editorial restructuring | Sol |
| Independent review of important work | Sol or GPT-5.5 |
| Small UI experiments | Codex Spark |
| Coding-specialist autonomous loop | GPT-5.3-Codex |

## A model workflow for a long-form research primer

For a document like the comparative religion primer, model choice works best as a division of labour. The strongest model should handle judgement, synthesis, and review. Cheaper models should handle bounded research, routine drafting, and mechanical checks. Tools and source quality matter just as much as model choice: a capable model cannot compensate for missing evidence or an unclear editorial brief.

### Recommended workflow

1. **Scope and architecture — GPT-5.6 Sol.** Define the audience, the comparison framework, the section structure, and the boundaries of the project before drafting begins. This is where the model should identify likely blind spots, such as treating a tradition as internally uniform or using one religion's categories as the template for all the others.

2. **Parallel research briefs — GPT-5.6 Terra.** Assign separate, tightly scoped briefs to individual researchers: Judaism, Christianity and the ancient churches, Protestant families, Islam, Hinduism, Sikhism, Buddhism, Shinto, and the comparative themes. Ask for source-backed notes, terminology, areas of internal diversity, and unresolved questions rather than polished prose.

3. **High-risk research and source triage — GPT-5.6 Sol.** Use Sol for contested history, classification disputes, ancient Christian divisions, colonial and post-colonial questions, and any topic where a neat summary is likely to be misleading. It should also compare the research briefs and identify contradictions before drafting.

4. **Section drafting — GPT-5.6 Terra.** Draft ordinary sections from approved outlines and source packets. A mid-tier general model is usually sufficient when the evidence, audience, length, and style are explicit.

5. **Whole-document synthesis — GPT-5.6 Sol.** Use Sol for the introduction, transitions, comparative chapters, conclusion, and any section that must reconcile several traditions. These passages require awareness of the document as a whole rather than knowledge of one subject in isolation.

6. **Independent editorial review — GPT-5.6 Sol or GPT-5.5.** Give a separate agent the complete document and ask it to challenge the work. It should look for factual overstatement, uneven coverage, inherited categories, abrupt transitions, empty or underdeveloped subsections, and prose that reads like a reference manual rather than an explanation.

7. **Repository and build work — GPT-5.3-Codex or GPT-5.6 Terra.** Use a coding-focused model for Markdown edits, heading changes, Just targets, build commands, and debugging. The task is procedural and tool-driven, so literary ability is less important than reliable repository navigation and implementation loops.

8. **Mechanical checks — GPT-5.6 Luna and shell tools.** Use Luna, `rg`, and ordinary scripts for heading consistency, repeated terminology, spelling variants, section lengths, and simple cross-reference checks. These tasks are too mechanical to justify a frontier model.

9. **Rendered-output review — Terra or Sol.** Build the HTML and PDF, inspect the rendered result, and use Sol when a layout or structural problem is difficult to diagnose. A document is not finished when the Markdown is correct; the produced artefacts also need to be readable.

10. **Human review.** The final judgement should remain human, especially for religion, history, politics, and other subjects involving living communities. The reviewer decides whether the balance, tone, and emphasis are fair—not merely whether the sentences are fluent.

## What we actually did on the comparative religion primer

The actual process was successful, but it was more iterative and top-heavy than the workflow above:

> draft → user identifies weaknesses → high-quality expansion → editorial review → rendering and QA

The document began with a broad structure covering authority, doctrine, structure, practice, and liturgy. It was then expanded in response to feedback, particularly around Protestant families, Eastern and Oriental Orthodoxy, Coptic and other ancient churches, Christianity in Africa and the Middle East, and the need for more explanatory prose.

Subagents were used most heavily for the later editorial work. The work record includes a GPT-5.5 editorial pass and a GPT-5.6 Sol editorial pass. Those reviews helped expand thin areas, replace some reference-like tables with narrative explanation, add stronger transitions and chapter openings, and check the document as a whole.

The repository and production work was handled through the existing project tools: Markdown source edits, Just targets, containerised rendering, and visual inspection of the HTML and PDF. This was an appropriate use of tools and avoided spending a frontier model on every mechanical operation.

The main difference from the recommended workflow is that research and drafting were not cleanly separated into independent, source-backed packets at the outset. As a result, several predictable weaknesses emerged in the first substantial version: uneven depth, underdeveloped Christian branches, thin transitions, and sections that were technically complete but not sufficiently readable. User feedback was essential in exposing those issues.

The later editorial passes corrected the problems effectively. The result is a good example of using a strong model where judgement matters, but the process could have been cheaper and more predictable if Terra research agents had mapped the individual traditions before the first full draft and Sol had reviewed that map before prose generation.

### A more efficient allocation for a repeat project

For a similar primer, the practical allocation would be:

- **GPT-5.6 Sol:** project architecture, difficult or contested research, cross-tradition synthesis, and final editorial review;
- **GPT-5.6 Terra:** parallel research briefs and most first-draft sections;
- **GPT-5.5:** an independent second editorial opinion when continuity or comparison with earlier work is useful;
- **GPT-5.3-Codex:** repository edits, build configuration, and tool-driven debugging;
- **GPT-5.6 Luna:** high-volume extraction and mechanical consistency checks;
- **Human reviewer:** scope, fairness, emphasis, and final approval.

This is not a rigid hierarchy. If Terra produces a strong section with good evidence, it does not need to be rewritten by Sol merely because Sol is available. Escalation is most valuable when the task involves ambiguity, interacting constraints, contested interpretation, or a costly error.

## API cost versus subscription cost

The dollar figures above are API list prices. They are not necessarily what a person pays through a ChatGPT or Codex subscription.

In the subscription interface, model use is generally governed by plan entitlements, quotas, rate limits, and usage windows. Account-specific limits and remaining quota are not visible to me, so the exact cost to our account cannot be inferred from API pricing alone.

There is no useful universal cost ranking for our Codex work. Input and output tokens have different API prices, and a real agent run may also involve repeated context, reasoning tokens, tool calls, and repair cycles. A model with a lower price per token can therefore cost more overall if it needs more attempts to complete the task.

For API billing purposes only, the input prices from lowest to highest are Luna ($0.20), GPT-5.3-Codex ($1.75), Terra ($2), Sol ($4), and GPT-5.5 ($5) per million tokens. The output prices are Luna ($1.20), Terra ($12), GPT-5.3-Codex ($14), Sol ($20), and GPT-5.5 ($30). GPT-5.5 appears at the expensive end of those lists because of its API price; that is not a ranking of capability, quality, or practical Codex value.

For example, a request using 100K input tokens and 20K output tokens would cost approximately $0.44 with Terra and $0.46 with GPT-5.3-Codex at the listed API rates. The actual impact on a Codex subscription cannot be inferred from those figures: subscriptions use plan entitlements, quotas, and usage windows rather than exposing these API prices directly. The product’s own usage display is the authority for account-specific consumption.

## Sources

- [OpenAI Models](https://developers.openai.com/api/docs/models) — current model family and official positioning.
- [OpenAI model comparison](https://developers.openai.com/api/docs/models/compare) — token pricing, context windows, and supported features.
- [GPT-5.5 model documentation](https://developers.openai.com/api/docs/models/gpt-5.5) — GPT-5.5 capabilities and pricing.
- [GPT-5.3-Codex model documentation](https://developers.openai.com/api/docs/models/gpt-5.3-codex) — coding specialisation and pricing.
- [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model) — reasoning controls and model-selection guidance.
- [Codex use cases](https://developers.openai.com/codex/use-cases) — Codex Spark’s documented use case.
