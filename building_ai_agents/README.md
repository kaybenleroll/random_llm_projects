# Building Autonomous AI Agents

A primer and reference collection covering how autonomous AI agents work, how LLMs power them, and how to build them.

## Documents

| File | Purpose |
|---|---|
| [`ai_agents_comprehensive_primer.md`](ai_agents_comprehensive_primer.md) | **Start here.** Accessible end-to-end primer: fundamentals, execution loops, tools, memory, patterns, challenges, and how to build your first agent |
| [`agent_quick_reference.md`](agent_quick_reference.md) | Developer cheat sheet: pattern selection matrices, code snippets, framework comparison, error handling strategies |

## Rendered Outputs

HTML and PDF versions are generated via [pandoc](https://pandoc.org/) using the `Justfile`. Requires [Podman](https://podman.io/) with the pandoc container images.

The canonical source file, [`ai_agents_comprehensive_primer.md`](ai_agents_comprehensive_primer.md), is intentionally kept renderable to both HTML and PDF from the same markdown content.

For diagrams, fenced `mermaid` blocks are supported through a Pandoc Lua filter. If `mmdc` (Mermaid CLI) is available, diagrams are rendered to images automatically during build; otherwise, Mermaid blocks are left as code blocks without failing the build.

In this project, HTML and PDF rendering both run through the local `localhost/pandoc-latex-fonts:latest` image, which includes Mermaid CLI and Chromium. Build that image once before rendering:

```sh
just build-pdf-image  # build local render image (required once, or after Dockerfile changes)
just all          # build HTML + PDF for the main primer
just all-docs     # build HTML for the quick reference
just rebuild      # clean and rebuild everything
just pull-images  # pre-fetch pandoc container images
```

## File Structure

```
building_ai_agents/
├── ai_agents_comprehensive_primer.md   # Main primer document
├── agent_quick_reference.md            # Developer cheat sheet
├── Justfile                            # Build targets (HTML + PDF via pandoc)
├── doc_template.html                   # Pandoc HTML template
└── pandoc_compact_code.latex           # LaTeX fragment for compact code blocks
```

**Purpose:** Comprehensive technical primer with depth
**Best for:** Understanding concepts, research, background context

**Section Breakdown:**

| Section | Purpose | Writer Use Case |
|---------|---------|-----------------|
| 1. Core Components | Architecture overview + layered breakdown | High-level architecture docs |
| 2. LLM Integration | How LLMs function in agent systems | "Why LLMs?" explainer |
| 3. Design Patterns | ReAct, tool-use, hierarchical planning | Pattern comparison guide |
| 4. Agent Lifecycle | Execution loops, state management | Workflow documentation |
| 5. Tool Systems | Tool definition, schema, execution | API integration guide |
| 6. Memory Management | Short/long-term memory, retrieval | Data storage architecture |
| 7. Real-World Examples | Framework comparison, code samples | "Getting started" guide |
| 8. Challenges | Known limitations, edge cases | "Common pitfalls" section |
| 9. Evaluation | Benchmarks, metrics, monitoring | Testing & validation docs |
| 10. Emerging Patterns | Future directions, cutting edge | Roadmap & research |

### Document 2: `agent_quick_reference.md`
**Purpose:** Practical quick-reference for decision-making
**Best for:** Decision matrices, checklists, implementation specifics

**Content Breakdown:**

| Section | Purpose | Writer Use Case |
|---------|---------|-----------------|
| Pattern Selection | Decision trees for which pattern to use | "Choose your architecture" guide |
| Tool Integration | Code patterns for tool execution | Implementation cookbook |
| Memory Patterns | Memory architecture examples | Storage design guide |
| Error Handling | Failure modes & recovery strategies | Troubleshooting guide |
| Framework Selection | Comparison table for frameworks | Product selection guide |
| Evaluation Metrics | Precise metric definitions | Testing & validation specs |
| Monitoring Queries | SQL for dashboards | Observability setup |
| Common Pitfalls | 8 key mistakes + solutions | Best practices guide |
| Implementation Checklist | Week-by-week roadmap | Project management |
| Cost Estimation | Budget calculations | Operational planning |
| Testing Strategy | Unit/integration/E2E approaches | QA planning |
| Deployment Checklist | Pre/during/post deployment steps | Release procedures |
| Glossary | 20 key terms defined | Reference material |

---

## How to Use These Materials

### 1. Writing a "Getting Started" Guide
**Read:**
- Primer: Section 7.2 (Practical Example: Research Agent)
- Quick Ref: "MVP Agent" checklist

**Extract:**
- Code examples (Pydantic AI style)
- Week-by-week roadmap
- Essential components needed

---

### 2. Writing Architecture Documentation
**Read:**
- Primer: Section 1 (Core Components) + Section 4 (Lifecycle)
- Primer: Section 3 (Design Patterns)
- Quick Ref: Pattern Selection Guide

**Extract:**
- Layered architecture diagram (adapt the ASCII diagram)
- Pattern comparison table
- Framework selection matrix

---

### 3. Writing API/Tool Integration Docs
**Read:**
- Primer: Section 5 (Tool/Action Systems)
- Primer: Section 5.3 (Reliability)
- Quick Ref: Tool Integration Patterns

**Extract:**
- Tool schema examples
- Error handling strategies
- Validation & retry patterns

---

### 4. Writing Evaluation/Testing Docs
**Read:**
- Primer: Section 9 (Evaluation & Monitoring)
- Quick Ref: Evaluation Metrics Definitions
- Quick Ref: Testing Strategy

**Extract:**
- Benchmark descriptions (HotpotQA, etc.)
- Metric formulas & thresholds
- Test case templates

---

### 5. Writing Production/Operations Docs
**Read:**
- Primer: Section 8.2-8.4 (Challenges)
- Quick Ref: Monitoring Dashboard Queries
- Quick Ref: Common Pitfalls & Solutions
- Quick Ref: Deployment Checklist

**Extract:**
- Alert thresholds & formulas
- SQL queries for dashboards
- Incident response procedures

---

### 6. Writing Troubleshooting/FAQ
**Read:**
- Primer: Section 8 (Challenges)
- Quick Ref: Common Pitfalls & Solutions
- Primer: Section 9.4 (Human Evaluation Setup)

**Extract:**
- Problem-solution pairs
- Root cause analysis
- Resolution strategies

---

## Key Concepts to Emphasize (in any document)

### 1. **Agent ≠ Chatbot**
Agents:
- Take **actions** in the world, not just generate text
- Operate autonomously toward goals
- Learn from execution failures
- Maintain persistent memory

Chatbots:
- Generate text responses
- Stateless per conversation
- No tool integration
- No learning loop

**Where to mention:** Any "What is an agent?" intro section

---

### 2. **The Importance of Tool Grounding**
Why it matters:
- Hallucination is THE biggest problem in agent systems
- Grounding means: every claim verified by a tool call
- Trade-off: slower but correct vs. fast but wrong

**Where to mention:** 
- Challenges section
- Best practices guides
- Design pattern explanations

---

### 3. **Cost is Competitive Advantage**
Cost dynamics:
- Multi-step reasoning = 10-20 LLM calls typical
- Context window size = input cost driver
- Compression saves 40-60% of costs

**Where to mention:**
- Framework selection (more efficient frameworks)
- Optimization guide
- Operational planning

---

### 4. **Evaluation is Hard**
Why:
- "Correct" answer context-dependent
- LLM self-evaluation unreliable
- Human evaluation expensive

**Solution:** Combination approach
- Automated metrics (success rate, cost)
- Human eval on sample (5-10% of tasks)
- Domain expert review for sensitive domains

**Where to mention:**
- Testing strategy
- QA procedures
- Monitoring philosophy

---

## Practical Examples You Can Directly Use

### Code Examples Ready to Adapt

**From Primer:**
- Section 7.2: Pydantic AI research agent (70 lines)
- Section 7.3: CrewAI multi-agent system (40 lines)

**From Quick Ref:**
- Tool validation & retry logic (15 lines)
- Memory compression pattern (20 lines)
- Error detection strategies (10 lines)
- Monitoring dashboard queries (3 SQL examples)

---

### Diagrams You Can Adapt

**ASCII Diagrams:**
- Agent architecture layers (5 layers)
- Execution loop flow
- Memory hierarchy

**Tables:**
- Pattern selection matrix (6×3)
- Framework comparison (4×4)
- Evaluation metrics (6 key metrics)
- Failure types & recovery (7 scenarios)

---

### Checklists You Can Reuse

**For Different Audiences:**

**For Developers:**
- "MVP Agent" checklist (Week 1)
- Implementation checklist (4 weeks)
- Testing checklist (unit/integration/E2E)

**For Operators:**
- Deployment checklist (pre/during/post)
- Monitoring setup
- Alert configuration

**For Researchers:**
- Benchmark datasets
- Evaluation methodology
- Common pitfalls

---

## Section Mapping by Document Type

### "What is an Agent?" (Conceptual Document)
**Use:**
- Primer 1.1-1.2 (components)
- Primer 2.1 (LLM role)
- Quick Ref Glossary
- Key concepts: Agent ≠ Chatbot

**Length:** 2-3 pages
**Audience:** Non-technical stakeholders

---

### "Building Your First Agent" (Tutorial)
**Use:**
- Primer 7.2 (code example - Pydantic AI)
- Primer 4.1 (execution loop)
- Quick Ref: MVP checklist
- Quick Ref: Common Pitfalls

**Length:** 5-8 pages
**Audience:** Developers
**Deliverable:** Runnable code + explanations

---

### "Architecture Patterns" (Reference)
**Use:**
- Primer 3 (all patterns)
- Primer 4.2 (state management)
- Quick Ref: Pattern selection guide
- Quick Ref: Framework selection matrix

**Length:** 10-15 pages
**Audience:** Architects
**Deliverable:** Decision trees, trade-off analysis

---

### "Agent Evaluation & Metrics" (Testing Guide)
**Use:**
- Primer 9 (evaluation frameworks)
- Quick Ref: Evaluation metrics definitions
- Quick Ref: Testing strategy
- Quick Ref: Monitoring dashboard queries

**Length:** 8-10 pages
**Audience:** QA/Analytics engineers
**Deliverable:** Metric definitions, query templates

---

### "Production Deployment" (Operations Guide)
**Use:**
- Primer 8.2-8.4 (challenges)
- Primer 9.3 (monitoring)
- Quick Ref: Monitoring queries
- Quick Ref: Deployment checklist
- Quick Ref: Common pitfalls

**Length:** 10-12 pages
**Audience:** DevOps/SRE
**Deliverable:** Runbooks, alert configs

---

### "Troubleshooting Guide" (Support Document)
**Use:**
- Primer 8 (challenges)
- Quick Ref: Common pitfalls & solutions
- Quick Ref: Error handling strategies
- Primer 4.3 (stopping conditions)

**Length:** 6-8 pages
**Audience:** Support/Operations teams
**Deliverable:** Problem-solution matrix

---

## Content Reusability

### Elements You Can Copy Directly
- All code examples (Pydantic AI, CrewAI)
- SQL monitoring queries
- Checklists (MVP, deployment, testing)
- Metric definitions
- Glossary terms

### Elements That Need Adaptation
- Diagrams (use as templates, adapt to your context)
- Examples (customize for your domain)
- Thresholds (tune based on your metrics)
- Frameworks (highlight ones you support)

### Elements for Inspiration Only
- Framework comparisons (add your choices)
- Cost calculations (use your pricing)
- Monitoring dashboards (customize to your stack)

---

## Common Writing Mistakes to Avoid

### 1. Treating Agent = Chatbot
❌ "The agent responds to user queries"
✅ "The agent takes actions toward user goals"

### 2. Ignoring Hallucination Risk
❌ "The agent can search the web"
✅ "The agent grounds answers in tool results to prevent hallucination"

### 3. Oversimplifying Tool Integration
❌ "The agent can call any tool"
✅ "The agent calls validated tools with schema-checked arguments, with automatic retry on validation errors"

### 4. Skipping Cost Implications
❌ "Multi-turn agentic loops"
✅ "Each turn costs ~$0.02, so 10-turn workflow ≈ $0.20 per execution"

### 5. Treating Evaluation as Binary
❌ "The system is 90% accurate"
✅ "Task success rate: 87% (n=1000), human eval score: 4.1/5, cost: $0.18 per task"

---

## Document Maintenance

As you write, keep this guide updated with:

- **New patterns discovered:** Add to Quick Ref Pattern Selection
- **Frameworks you support:** Update Framework Selection Matrix
- **Your metrics:** Update Evaluation Metrics with your thresholds
- **Your pitfalls:** Add to Common Pitfalls section
- **Your checklists:** Customize Implementation Checklist

---

## Quick Copy-Paste References

### For Every Agent Tutorial, Include
```
💡 Key Insight: [Pick one from Primer section 1-3]

⚠️ Common Mistake: [Pick one from Challenges section]

📊 Success Metrics: [Pick relevant metrics from Section 9.1]

🚀 Next Steps: [Link to advanced pattern]
```

### For Every Architecture Decision Doc, Include
```
Trade-off Analysis:
  Pro: [from pattern description]
  Con: [from limitations]
  Cost: [from section 10]
  Complexity: [from framework matrix]

When to Use:
  ✅ [use case 1]
  ✅ [use case 2]
  ❌ [anti-pattern 1]
```

### For Every Monitoring Setup, Include
```
Dashboard Queries:
  1. Success Rate: [include SQL]
  2. Cost Anomalies: [include SQL]
  3. Tool Health: [include SQL]

Alert Thresholds:
  - Success rate drops 10% → warn
  - Cost per task 20% above baseline → warn
  - Tool error rate >5% → critical
```

---

## Final Notes for Technical Writers

1. **These materials are living documents.** As the agent field evolves, framework updates happen, new patterns emerge—revisit these guides quarterly.

2. **Customize for your audience.** Non-technical stakeholders need "agent vs. chatbot" explained; architects need pattern trade-offs; operators need monitoring queries.

3. **Emphasize the practical.** The field is moving fast. Focus on what teams are actually building right now (2026), not speculative future directions.

4. **Ground everything in examples.** Agent architecture is abstract. Code examples, real frameworks, and concrete metrics make concepts stick.

5. **Cost matters.** Every design decision has cost implications. Include cost thinking in every document where relevant.

6. **Hallucination is THE problem.** If nothing else, communicate that grounding in tool execution is the most important reliability feature.

---

## Questions This Reference Answers

- "What pattern should we choose?" → Quick Ref Pattern Selection Matrix
- "How do we monitor in production?" → Quick Ref Monitoring Queries
- "What are common mistakes?" → Quick Ref Common Pitfalls
- "How much will this cost?" → Quick Ref Cost Estimation
- "What should our first prototype look like?" → Quick Ref MVP Checklist + Primer 7.2
- "How do we test agents?" → Quick Ref Testing Strategy + Primer 9
- "What frameworks exist?" → Quick Ref Framework Matrix + Primer 7.1
- "How do we handle failures?" → Quick Ref Error Handling + Primer 8
- "What's a successful agent?" → Primer 9 + Quick Ref Evaluation Metrics

---

You're ready to start writing. Pick a document type above, use the "Read" section to gather material, and extract the relevant content. All code is production-ready, all metrics are practical, all checklists are proven.

Good luck! 🚀
