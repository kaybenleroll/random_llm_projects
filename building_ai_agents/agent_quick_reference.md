# Agent Architecture Quick Reference & Decision Frameworks

## Pattern Selection Guide

### ReAct (Reasoning + Acting)
**When to use:**
- Knowledge-intensive tasks (Q&A, fact verification)
- Need interpretable decision traces
- User-facing applications requiring transparency

**Execution Model:**
```
Thought → Action → Observation → (loop)
```

**Pros:** Interpretable, self-correcting, reduces hallucination
**Cons:** Verbose, sequential (no parallelism), requires clean action space

**Code Pattern:**
```python
agent_loop:
  thought = llm.think(context)
  action = llm.select_action(thought)
  observation = execute(action)
  context.append(observation)
```

---

### Tool-Use Loop (Agentic Loop)
**When to use:**
- Complex tasks with multiple tool dependencies
- Open-ended environments
- When success criteria clear but path uncertain

**Execution Model:**
```
LLM → Tool Calls → Append Results → Loop Until Done
```

**Pros:** Flexible, general-purpose, handles complex scenarios
**Cons:** Can hit maximum iterations, hard to reason about long-term outcomes

**Code Pattern (Pydantic AI):**
```python
@agent.tool
async def search(query: str) -> str:
    """Search for information."""
    return await api.search(query)

result = await agent.run("Find info about X", deps=deps)
```

---

### Hierarchical Planning (LLM+P)
**When to use:**
- Well-defined action spaces with preconditions
- Robotics/structured domains
- When long-horizon planning critical

**Execution Model:**
```
LLM → Translate to PDDL → Symbolic Planner → LLM → Execute
```

**Pros:** Better long-horizon planning, less hallucination on action sequencing
**Cons:** Requires domain knowledge (PDDL), inflexible for novel domains

---

### Reflexion (Self-Correcting)
**When to use:**
- Iterative problem-solving tasks
- When failure patterns predictable
- Learning from mistakes important

**Execution Model:**
```
Execute → Evaluate → Reflect → Retry with Reflection
```

**Pros:** Improves over multiple attempts, automatic failure detection
**Cons:** Slower (multiple attempts), requires reliable evaluator

---

### Multi-Agent Orchestration (CrewAI Crews)
**When to use:**
- Need specialized agent roles
- Complex workflows with delegation
- Team-like collaboration required

**Execution Model:**
```
Task → Agent Selection → Execution → Next Task
```

**Pros:** Natural role assignment, clear responsibilities, easy to extend
**Cons:** Coordination overhead, harder to debug

---

## Tool Integration Patterns

### Synchronous Tool Execution
```python
# Simple: one tool call at a time
tools_results = []
for tool_call in response.tool_calls:
    result = execute_tool(tool_call)
    tools_results.append(result)
```

**Pros:** Simple, deterministic order
**Cons:** Slow for independent tools

---

### Parallel Tool Execution
```python
# Faster: concurrent execution
import asyncio

results = await asyncio.gather(
    *[execute_tool(tc) for tc in response.tool_calls]
)
```

**Pros:** Fast for independent tools
**Cons:** Non-deterministic ordering, harder to debug

---

### Tool Validation & Retry
```python
async def execute_tool_with_retry(tool_call, max_retries=2):
    for attempt in range(max_retries):
        try:
            # Validate arguments before execution
            validated_args = validate_schema(tool_call.args)
            result = await execute(tool_call.name, validated_args)
            return {"success": True, "result": result}
        except ValidationError:
            if attempt < max_retries - 1:
                # Ask LLM to fix arguments
                corrected = await llm.correct_tool_args(tool_call, error)
                tool_call = corrected
        except ToolError as e:
            return {"success": False, "error": str(e)}
```

---

## Memory Architecture Patterns

### Short-Term: Context Window
**What to keep:**
- Latest 5-10 interactions (full detail)
- Current task description
- Active dependencies

**When to compress:**
- Approaching 80% of context limit
- Task depth > 15 steps

```python
if len(conversation) > 20:
    # Summarize older interactions
    summary = await llm.summarize(conversation[:-10])
    conversation = [summary] + conversation[-10:]
```

---

### Long-Term: Vector Store
**What to store:**
- Task execution summaries
- Successful action sequences
- Common failure modes + solutions

**Retrieval pattern:**
```python
# On new task:
relevant_memories = vector_store.search(
    query=new_task_embedding,
    top_k=3,
    filters={"agent_id": current_agent}
)

# Include in context:
context += "\n\nSimilar past tasks:\n"
for memory in relevant_memories:
    context += f"- {memory.summary}\n"
```

**Scoring function:**
```
score = 0.4 * recency + 0.4 * relevance + 0.2 * importance
```

---

## Error Handling & Recovery

### Failure Detection Strategies

| Failure Type | Detection | Recovery |
|---|---|---|
| Invalid tool args | Schema validation | Ask LLM to retry with error message |
| Tool timeout | Execution timeout >30s | Fallback tool or skip |
| Hallucinated facts | No tool backing | Reject in prompt, ask for sources |
| Infinite loop | Same action 3x | Insert reflection, suggest alternatives |
| Context exhaustion | Token count > limit | Summarize, move to long-term memory |
| API rate limit | 429 response | Exponential backoff, queue |

### Reflection Template
```
If max_iterations reached without success:
  1. Show agent failed trajectory
  2. Ask: "Why did this approach fail?"
  3. Generate reflection instruction
  4. Inject into next attempt
  
Example reflection:
  "Previous approach used only surface-level searches. This domain 
   requires cross-referencing multiple sources. Try combining results 
   from at least 3 different sources before synthesizing answer."
```

---

## Framework Selection Matrix

| Dimension | Best Option | Trade-off |
|-----------|-------------|----------|
| **Simplicity** | Pydantic AI | Less advanced orchestration |
| **Multi-agent** | CrewAI | Higher overhead |
| **Workflow control** | LangGraph | More boilerplate |
| **Type safety** | Pydantic AI | Python-only |
| **Observability** | Pydantic AI + Logfire | Proprietary (not required) |
| **Cost optimization** | LangGraph (more control) | Requires manual tuning |

---

## Evaluation Metrics Definitions

### Task Success Rate
```
= (completed_successfully / total_attempted) * 100%

Threshold: 
  - MVP: >70%
  - Production: >90%
  - Enterprise: >95%
```

### Average Steps to Success
```
= sum(steps_for_successful_tasks) / count(successful)

Benchmark: 5-10 steps typical for complex tasks
Optimization: Reduce redundant tool calls
```

### Hallucination Rate
```
= (claims_without_tool_backing / total_claims) * 100%

Acceptable: <5%
Detection: Analyze final output for unsourced claims
```

### Tool Use Accuracy
```
= (correct_argument_calls / total_tool_calls) * 100%

Target: >95%
Improvement: Better instruction + schema validation
```

### Cost per Task
```
= (input_tokens + output_tokens * 1.5) * price_per_1k_tokens

Optimization:
  - Cache system prompts
  - Compress conversation history
  - Use smaller models for simple tasks
```

---

## Monitoring Dashboard Queries

### Success Rate Trend
```sql
SELECT
  DATE(created_at) as date,
  COUNT(*) as total,
  SUM(CASE WHEN success=true THEN 1 ELSE 0 END) as successful,
  (SUM(CASE WHEN success=true THEN 1 ELSE 0 END)::float / COUNT(*)) * 100 as success_rate
FROM agent_executions
WHERE created_at > NOW() - INTERVAL 30 days
GROUP BY DATE(created_at)
ORDER BY date DESC
```

### Cost Anomalies
```sql
SELECT
  agent_id,
  AVG(cost_usd) as avg_cost,
  STDDEV(cost_usd) as stddev_cost,
  MAX(cost_usd) as max_cost
FROM agent_executions
WHERE created_at > NOW() - INTERVAL 7 days
HAVING STDDEV(cost_usd) > AVG(cost_usd) * 0.5
ORDER BY max_cost DESC
```

### Tool Health
```sql
SELECT
  tool_name,
  COUNT(*) as calls,
  SUM(CASE WHEN success=true THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
  AVG(latency_ms) as avg_latency_ms,
  MAX(latency_ms) as max_latency_ms
FROM tool_executions
WHERE created_at > NOW() - INTERVAL 7 days
GROUP BY tool_name
ORDER BY success_rate ASC, max_latency_ms DESC
```

---

## Common Pitfalls & Solutions

| Pitfall | Symptom | Solution |
|---------|---------|----------|
| **Token explosion** | Costs triple unexpectedly | Implement conversation compression; use vector store |
| **Tool argument errors** | Many tool calls fail validation | Add schema validation before execution; better error messages |
| **Infinite loops** | Agent gets stuck repeating | Detect repeated actions; inject reflection |
| **Hallucination** | False claims in output | Require tool backing; audit claims against tools |
| **Slow execution** | Task takes >1 minute | Parallelize independent tool calls; use smaller model |
| **Drift over time** | Quality degrades in production | Monitor human eval samples; retrain on recent data |
| **Model version mismatch** | Unexpected behavior changes | Pin model versions; maintain compatibility layer |

---

## Quick Implementation Checklist

### MVP Agent (Week 1)
```
☐ Choose model (Claude 3.5 Sonnet recommended)
☐ Define 3-5 core tools
☐ Write system prompt
☐ Implement basic agentic loop
☐ Test with 10 sample tasks
☐ Manual success rate measurement
```

### Enhanced Agent (Week 2-3)
```
☐ Add tool error handling & retries
☐ Implement reflection on failures
☐ Add conversation history management
☐ Integrate vector store for memory
☐ Set up structured logging
☐ Create basic dashboard
```

### Production Ready (Week 4+)
```
☐ Implement rate limiting & quotas
☐ Add human-in-the-loop for critical actions
☐ Set up comprehensive monitoring
☐ Create incident response runbooks
☐ Establish SLA metrics
☐ User feedback loop
☐ A/B test improvements
```

---

## Cost Estimation Framework

### Per-Task Cost Calculation
```
Base cost = (input_tokens + output_tokens * 1.5) / 1000 * price_per_1k

Example (Claude 3.5 Sonnet):
  Input: 2000 tokens ($0.003 per 1k) = $0.006
  Output: 500 tokens ($0.015 per 1k) = $0.0075
  Total: $0.0135 per task
```

### Monthly Budget Projection
```
Monthly = tasks_per_day * avg_cost_per_task * 30 * growth_factor

Example:
  1000 tasks/day * $0.015 * 30 = $450/month base
  With 20% monthly growth: $450 * (1.2^12) = ~$25k/year
```

### Optimization ROI
```
Compression savings = (original_tokens - compressed_tokens) * price_per_token * tasks_per_month

If saving 500 tokens per task:
  500 * $0.000003 * 30,000 tasks/month = $45/month = $540/year
```

---

## Testing Strategy

### Unit Tests
```python
# Test individual tools
def test_search_tool():
    result = search("Python agents")
    assert len(result) > 0
    assert "relevance_score" in result[0]

# Test error handling
def test_tool_timeout():
    with timeout(1):
        result = slow_tool()
    assert result["error"] == "Timeout"
```

### Integration Tests
```python
# Test agent with tool suite
async def test_agent_research_task():
    agent = ResearchAgent()
    result = await agent.run(
        "Find latest AI research from 2026"
    )
    assert result.success == True
    assert len(result.sources) >= 3
```

### End-to-End Tests
```python
# Test agent on realistic scenarios
test_cases = [
    ("simple query", success_threshold=0.95),
    ("complex task", success_threshold=0.80),
    ("ambiguous request", success_threshold=0.70),
]

for task, threshold in test_cases:
    success_rate = run_trials(agent, task, n=10)
    assert success_rate >= threshold
```

### Human Evaluation
```
Sample 5-10% of production runs weekly
Rate on: Correctness, Completeness, Efficiency, Clarity
Pass/fail: Average rating >= 4/5
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] Manual QA on 20+ test cases
- [ ] Human review of edge cases
- [ ] Security audit (no data leaks)
- [ ] Rate limiting configured
- [ ] Error monitoring set up

### Deployment
- [ ] Blue-green deployment (new version parallel)
- [ ] Canary rollout (1% → 10% → 100%)
- [ ] Real-time monitoring active
- [ ] Rollback plan ready

### Post-Deployment
- [ ] Success rate > baseline
- [ ] Cost within budget
- [ ] No security incidents
- [ ] User feedback positive
- [ ] Scheduled review in 2 weeks

---

## Glossary

**Agent:** Autonomous system with LLM as decision-making core, tools for action, memory for context

**Tool Call:** Agent's request to execute external function (API, code, etc.)

**Trajectory:** Full sequence of thoughts, actions, and observations for one task execution

**Reflection:** Self-analysis of failure mode to improve future attempts

**Hallucination:** LLM generating false information not grounded in tool results

**Context Window:** Maximum tokens available to LLM for input + output

**Vector Store:** Database of semantic embeddings for similarity search

**Episodic Memory:** Storage of past task executions for pattern learning

**ReAct:** Pattern: Reason (think) → Act (do) → Observe (get result) → Repeat

**MRKL:** Modular reasoning system routing tasks to specialized expert tools

**A2A:** Agent-to-Agent communication protocol for inter-agent coordination

**MCP:** Model Context Protocol for standardized agent-tool interfaces

