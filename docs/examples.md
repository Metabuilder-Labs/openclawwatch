# Examples

The [`examples/`](../examples/) directory contains runnable agents for every supported integration, from single-provider basics to complex multi-agent workflows.

## Quick start

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-...
python examples/single_provider/anthropic_agent.py
```

After running any example:

```bash
ocw status       # agent session overview
ocw traces       # list all spans from the run
ocw cost --since 1h   # cost breakdown
ocw alerts       # any fired alerts
```

## Single provider

One integration per file. Simplest way to see `ocw` in action.

| Example | Env vars | Description |
|---|---|---|
| [`anthropic_agent.py`](../examples/single_provider/anthropic_agent.py) | `ANTHROPIC_API_KEY` | Tool-use agent with calculator and weather tools |
| [`openai_agent.py`](../examples/single_provider/openai_agent.py) | `OPENAI_API_KEY` | Function-calling agent with streaming response |
| [`gemini_agent.py`](../examples/single_provider/gemini_agent.py) | `GOOGLE_API_KEY` | Text summarization via Gemini Flash |
| [`bedrock_agent.py`](../examples/single_provider/bedrock_agent.py) | AWS creds | Claude on AWS Bedrock |
| [`openai_agents_sdk_agent.py`](../examples/single_provider/openai_agents_sdk_agent.py) | `OPENAI_API_KEY` | Multi-agent handoff via OpenAI Agents SDK |
| [`litellm_agent.py`](../examples/single_provider/litellm_agent.py) | `OPENAI_API_KEY` `ANTHROPIC_API_KEY` | Multi-provider routing via LiteLLM |

## Single framework

One framework integration per file. Shows how `ocw` captures framework-level spans.

| Example | Env vars | Description |
|---|---|---|
| [`langchain_agent.py`](../examples/single_framework/langchain_agent.py) | `OPENAI_API_KEY` | Tool-calling agent with calculator and word counter |
| [`langgraph_agent.py`](../examples/single_framework/langgraph_agent.py) | `OPENAI_API_KEY` | Plan-execute-review graph pipeline |
| [`crewai_agent.py`](../examples/single_framework/crewai_agent.py) | `OPENAI_API_KEY` | Researcher + writer crew collaboration |
| [`autogen_agent.py`](../examples/single_framework/autogen_agent.py) | `OPENAI_API_KEY` | Two-agent debate with back-and-forth |
| [`llamaindex_agent.py`](../examples/single_framework/llamaindex_agent.py) | `OPENAI_API_KEY` | RAG query engine over sample documents |

## Multi-integration

Complex real-world patterns combining multiple providers and frameworks.

| Example | Env vars | Description |
|---|---|---|
| [`router_agent.py`](../examples/multi/router_agent.py) | `ANTHROPIC_API_KEY` `OPENAI_API_KEY` `GOOGLE_API_KEY` | Routes tasks to the cheapest/best provider |
| [`research_team.py`](../examples/multi/research_team.py) | `ANTHROPIC_API_KEY` `OPENAI_API_KEY` | CrewAI agents with LangChain tools |
| [`rag_pipeline.py`](../examples/multi/rag_pipeline.py) | `OPENAI_API_KEY` `ANTHROPIC_API_KEY` | RAG with OpenAI-to-Anthropic fallback |

## Alerts and drift (no API keys needed)

These demonstrate real-time alerting and behavioral drift detection using simulated instrumentation. No LLM API keys required.

| Example | Description |
|---|---|
| [`sensitive_actions_demo.py`](../examples/alerts_and_drift/sensitive_actions_demo.py) | Fires alerts when agent calls sensitive tools |
| [`budget_breach_demo.py`](../examples/alerts_and_drift/budget_breach_demo.py) | Exceeds budget limits, shows cost alerts |
| [`drift_demo.py`](../examples/alerts_and_drift/drift_demo.py) | Builds baseline, then triggers drift detection |

```bash
python examples/alerts_and_drift/budget_breach_demo.py
ocw alerts       # see budget-breach alerts
ocw cost --since 1h   # see cost tracking
```

## Which examples need `ocw serve`?

Most examples use in-process telemetry. These use OTLP HTTP and require the server running:

- `openai_agents_sdk_agent.py`
- `llamaindex_agent.py`
- `rag_pipeline.py`

```bash
ocw serve &   # start before running these
```

See [`examples/README.md`](../examples/README.md) for extra deps and detailed setup notes.
