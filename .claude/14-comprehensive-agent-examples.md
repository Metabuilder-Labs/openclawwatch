# Task: Create example agents in `examples/`

## Structure

Create an `examples/` top-level directory organized by complexity:

```
examples/
├── README.md
├── single_provider/
│   ├── anthropic_agent.py
│   ├── openai_agent.py
│   ├── gemini_agent.py
│   ├── bedrock_agent.py
│   └── openai_agents_sdk_agent.py
├── single_framework/
│   ├── langchain_agent.py
│   ├── langgraph_agent.py
│   ├── crewai_agent.py
│   ├── autogen_agent.py
│   └── llamaindex_agent.py
├── multi/
│   ├── router_agent.py
│   ├── research_team.py
│   └── rag_pipeline.py
└── alerts_and_drift/
    ├── sensitive_actions_demo.py
    ├── budget_breach_demo.py
    └── drift_demo.py
```

---

## Cross-Cutting Guidelines

These apply to ALL examples.

### 1. Env var gate

Every example that requires an API key must check at startup and exit with a clear message:

```python
import os, sys

if not os.environ.get("OPENAI_API_KEY"):
    sys.exit("Set OPENAI_API_KEY to run this example.\n  export OPENAI_API_KEY='sk-...'")
```

No cryptic stack traces. Fail fast, fail helpfully.

### 2. `ocw serve` check (for OTLP-based integrations)

`openai_agents_sdk_agent.py` and `llamaindex_agent.py` export via OTLP HTTP to `ocw serve`, not in-process. These must check connectivity at startup:

```python
import httpx, sys

try:
    httpx.get("http://127.0.0.1:8787/api/v1/traces", timeout=2)
except httpx.ConnectError:
    sys.exit(
        "This example requires ocw serve to be running.\n"
        "Start it with: ocw serve &"
    )
```

Do NOT start the server programmatically. Just check and exit with a clear message.

### 3. Observation block

Every example must end with a printed observation block:

```python
print("\n--- What to observe ---")
print("  ocw status          → see this agent's session")
print("  ocw traces          → see all spans from this run")
print("  ocw cost --since 1h → see cost breakdown")
```

### 4. Single-command runnable

Every example runs with: `python examples/<tier>/<name>.py`

### 5. All examples use `@watch()` decorator

So sessions show up in `ocw status` immediately.

### 6. Dependency comments

List extra pip deps in a comment at the top of each file. Example:
```python
# Extra deps: pip install langchain-core langchain-openai
```

---

## Single-Provider Examples

Each demonstrates one provider integration with `@watch()` and the relevant `patch_*` call.

| File | Integration | What it does |
|---|---|---|
| `anthropic_agent.py` | `patch_anthropic` | Tool-use agent — Claude calls functions (calculator, weather stub), shows tool call spans and cost tracking. Adapted from `tests/toy_agent/toy_agent.py` (do NOT move the original — copy and expand). |
| `openai_agent.py` | `patch_openai` | Chat agent that calls GPT-4o, streams a response, uses a tool (web search stub). Shows streaming + tool use spans. |
| `gemini_agent.py` | `patch_gemini` | Summarization agent — takes a long text, returns a summary via Gemini. Shows Google provider path. |
| `bedrock_agent.py` | `patch_bedrock` | **Advanced.** Agent that calls Claude-on-Bedrock via boto3. Shows AWS path with stream re-wrapping. See prominent setup note below. |
| `openai_agents_sdk_agent.py` | `patch_openai_agents` | Uses the OpenAI Agents SDK with a handoff between two agents. Shows native OTel integration path (no monkey-patching). Requires `ocw serve` running (uses OTLP HTTP export). |

### Bedrock setup note

`bedrock_agent.py` must include this prominent note at the top:

```python
"""
AWS Bedrock Agent Example — ADVANCED SETUP REQUIRED

Before running, you need:
1. AWS credentials configured (aws configure, or IAM role, or env vars
   AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)
2. A Bedrock-enabled AWS region (e.g., us-east-1, us-west-2)
3. Model access enabled in the AWS Bedrock console for the model you want
   to use (e.g., anthropic.claude-3-haiku-20240307-v1:0)

  export AWS_DEFAULT_REGION=us-east-1
  python examples/single_provider/bedrock_agent.py
"""
```

---

## Single-Framework Examples

Each demonstrates one framework integration showing how `ocw` captures framework-level spans.

| File | Integration | What it does |
|---|---|---|
| `langchain_agent.py` | `patch_langchain` | ReAct agent with a calculator and Wikipedia tool. The canonical LangChain pattern. |
| `langgraph_agent.py` | `patch_langgraph` | Multi-step graph: plan → research → draft → review. Shows graph-level span capture with conditional edges. |
| `crewai_agent.py` | `patch_crewai` | Two-agent crew: researcher + writer collaborating on a blog post. Shows multi-agent task orchestration. |
| `autogen_agent.py` | `patch_autogen` | Two ConversableAgents debating a topic with back-and-forth. Shows chat initiation + reply generation spans. |
| `llamaindex_agent.py` | `patch_llamaindex` | RAG pipeline: `SimpleDirectoryReader` + `VectorStoreIndex` with in-memory storage → query → synthesize answer. No FAISS. Shows native OTel instrumentation path. Requires `ocw serve` running (uses OTLP HTTP export). |

---

## Multi-Integration Examples

These are the showcase — real-world patterns combining multiple integrations. They should exercise `ocw` features heavily: cost tracking across providers, alerts, multi-agent sessions with different budgets.

### `router_agent.py` — Provider router
- Uses `patch_openai()` + `patch_anthropic()` + `patch_gemini()`
- Routes requests to different providers based on task type (quick Q&A → Gemini Flash, coding → Claude, creative → GPT-4o)
- **Shows:** cost comparison across providers in `ocw cost`, multi-provider spans in a single trace

### `research_team.py` — Multi-framework research team
- Uses `patch_anthropic()` + CrewAI for orchestration + LangChain for tool execution
- A "lead researcher" agent delegates sub-tasks to specialist agents, each with tools (web search stub, file reader, calculator)
- **Shows:** deep span trees, multi-agent session tracking, tool call patterns visible in `ocw tools`

### `rag_pipeline.py` — RAG with fallback
- Uses LlamaIndex `SimpleDirectoryReader` + `VectorStoreIndex` (in-memory, no FAISS) for indexing/retrieval + `patch_openai()` for generation + `patch_anthropic()` as fallback
- Include 3-4 small .txt files in `examples/multi/sample_docs/`
- Answers questions, falls back to Anthropic if OpenAI fails or exceeds token budget
- **Shows:** budget alerts firing, provider fallback visible in traces, schema validation on structured output

---

## Alerts and Drift Examples

These demonstrate the features that differentiate `ocw` from LangSmith, Langfuse, and every other tool. These are the most important examples for showing what makes this product unique.

**All alerts/drift examples use simulated instrumentation by default** — `record_llm_call()` and `record_tool_call()` from `ocw.sdk.agent`. This means:
- Zero API keys required
- Zero cost
- Runnable by anyone cloning the repo
- The point is demonstrating `ocw` features, not making real LLM calls

Each example should accept an optional `--live` flag (or `OCW_LIVE=1` env var) that switches to real API calls for users who want to see it end-to-end with actual providers.

### `sensitive_actions_demo.py` — Sensitive action alerts
- Agent that performs actions configured as sensitive: `send_email`, `delete_file`, `submit_form`
- Creates temp files, "sends" emails (writes to a log file), "submits" a form (prints to stdout)
- Include the companion `ocw.toml` snippet in a comment block showing how to configure the sensitive actions and alert channels
- Uses `record_tool_call()` for each sensitive action
- **Shows:** alerts firing in real time, visible in `ocw alerts`

### `budget_breach_demo.py` — Budget alerts
- Agent in a loop that deliberately exceeds a very low budget ($0.05 daily, $0.02 session)
- Uses `record_llm_call()` with high token counts to simulate expensive calls
- **Shows:** `ocw cost` tracking spend in real time, `ocw alerts` showing the budget breach, what happens when the limit is hit

### `drift_demo.py` — Behavioral drift detection
- Phase 1: Runs 12 identical "normal" sessions using `record_llm_call()` + `record_tool_call()` to build a statistical baseline (same agent_id, similar token usage, same tool sequence)
- Phase 2: Runs 1 anomalous session — different prompt that triggers 5x the normal token count and different tool calls
- All via `record_llm_call()` — zero cost, zero API keys
- **Shows:** `ocw alerts` showing DRIFT_DETECTED, baseline vs observed comparison

---

## `examples/README.md`

Create a README that:
- Lists every example with a one-line description
- Groups by tier (single provider → single framework → multi-integration → alerts/drift)
- Shows required env vars per example
- Marks which examples need `ocw serve` running
- Explains how to verify with `ocw` commands
- Notes that alerts/drift examples work with zero API keys

---

## Updates to existing files

- Do NOT move `tests/toy_agent/toy_agent.py` — copy and expand into `examples/single_provider/anthropic_agent.py`
- Add an "Examples" section to the repo `README.md` after "Quickstart" with a brief summary and link to `examples/`
- Update `CLAUDE.md` repo layout section to include `examples/`

---

## Verification

- Every example in `single_provider/` runs with just the relevant API key set
- Every example produces spans visible in `ocw traces`
- The alerts/drift examples run with zero API keys and produce alerts visible in `ocw alerts`
- Examples requiring `ocw serve` exit cleanly with instructions if server isn't running
- Examples missing required env vars exit cleanly with instructions
- `ruff check examples/` passes
- All existing tests still pass (no test modifications)
