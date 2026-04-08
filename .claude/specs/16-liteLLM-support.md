# Task: Add LiteLLM provider patch

## Context

LiteLLM is a popular abstraction layer that provides a unified `completion()` and `acompletion()` interface across 100+ LLM providers (OpenAI, Anthropic, Bedrock, Vertex, Cohere, Mistral, Ollama, etc.). Many agent builders use LiteLLM as their provider layer, meaning a single `patch_litellm()` integration gives `ocw` coverage across all of those providers with one patch.

## What to build

### 1. Integration file: `ocw/sdk/integrations/litellm.py`

Follow the exact same pattern as `ocw/sdk/integrations/openai.py` and `ocw/sdk/integrations/anthropic.py`. Study those files carefully — match the class structure, install/uninstall pattern, span attributes, and error handling.

**Patch targets:**
- `litellm.completion` — the synchronous completion function
- `litellm.acompletion` — the async completion function

**LiteLLM response shape:**
LiteLLM returns an OpenAI-compatible `ModelResponse` object. Key fields:
```python
response.usage.prompt_tokens      # input tokens
response.usage.completion_tokens  # output tokens
response.usage.total_tokens       # total
response.model                    # actual model used (may differ from requested)
```

LiteLLM also exposes `response._hidden_params` which contains:
```python
response._hidden_params["custom_llm_provider"]  # e.g. "anthropic", "openai", "bedrock"
```

Use `custom_llm_provider` to set the `gen_ai.provider.name` span attribute. This is the key value of this integration — a single patch that correctly attributes spans to the actual underlying provider.

**Model name parsing:**
LiteLLM uses prefixed model names: `anthropic/claude-haiku-4-5`, `bedrock/anthropic.claude-v2`, `openai/gpt-4o`, etc. Parse the model string:
- Set `gen_ai.request.model` to the full LiteLLM model string (e.g. `anthropic/claude-haiku-4-5`)
- If `custom_llm_provider` is available from the response, use that for `gen_ai.provider.name`
- Otherwise, infer provider from the model string prefix (everything before the first `/`)

**Streaming:**
LiteLLM streaming (`stream=True`) returns a `ModelResponseIterator`. Wrap it the same way `openai.py` wraps OpenAI streams — yield chunks, capture usage from the final chunk, end the span on exhaustion or error.

**Agent ID inheritance:**
Copy the agent_id and conversation_id inheritance from parent span, same as `anthropic.py` does.

**Span attributes to set:**
- `gen_ai.provider.name` — from `custom_llm_provider` or model prefix
- `gen_ai.request.model` — full model string from kwargs
- `gen_ai.response.model` — from `response.model` (actual model used)
- `gen_ai.usage.input_tokens` — from `response.usage.prompt_tokens`
- `gen_ai.usage.output_tokens` — from `response.usage.completion_tokens`
- `gen_ai.agent.id` — inherited from parent span
- `gen_ai.conversation.id` — inherited from parent span

### 2. Public function: `patch_litellm()`

```python
from ocw.sdk.integrations.litellm import patch_litellm

patch_litellm()  # patches both litellm.completion and litellm.acompletion
```

Follow the same pattern as `patch_openai()` in `openai.py` — call `ensure_initialised()`, create the integration instance, install it.

### 3. Register in `ocw/sdk/integrations/__init__.py`

Add `patch_litellm` to the module exports if there's an `__all__` or any registration pattern.

### 4. Tests: `tests/unit/test_litellm_integration.py`

Follow the test patterns from existing integration tests. Mock `litellm.completion` and `litellm.acompletion` to return fake `ModelResponse` objects and verify:

- Span is created with correct name (`invoke_llm`)
- Provider name is extracted correctly from `custom_llm_provider`
- Provider name falls back to model string prefix when `custom_llm_provider` is unavailable
- Input/output tokens are captured
- Model name is set correctly
- Streaming wrapper yields all chunks and captures usage on completion
- Errors set span status to ERROR and re-raise
- Agent ID and conversation ID are inherited from parent span
- `uninstall()` restores original functions

### 5. Example: `examples/single_provider/litellm_agent.py`

A simple example that demonstrates the LiteLLM patch routing to multiple providers:

```python
"""
LiteLLM multi-provider agent — demonstrates patch_litellm() with provider routing.

Required env vars:
    OPENAI_API_KEY      — for OpenAI calls
    ANTHROPIC_API_KEY   — for Anthropic calls

Usage:
    python examples/single_provider/litellm_agent.py
"""
```

The example should:
- Call `litellm.completion()` with 2-3 different provider-prefixed models (e.g. `openai/gpt-4o-mini`, `anthropic/claude-haiku-4-5`)
- Show that `ocw traces` correctly attributes each call to the right provider
- Include the standard observation block at the end
- Include env var gate at the top (check for at least one API key)

### 6. Documentation updates

- Add `patch_litellm` to the "Provider patches" section in `README.md`, under the existing patches
- Add a note that LiteLLM covers OpenAI-compatible providers, so users don't need both `patch_openai` and `patch_litellm`
- Add `litellm_agent.py` to `examples/README.md`
- Update `CLAUDE.md` if it lists integrations

### 7. Optional dependency

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
litellm = ["litellm>=1.40"]
```

---

## Double-counting prevention (contextvars)

When both `patch_litellm()` and `patch_openai()`/`patch_anthropic()` are active, the LiteLLM patch wins. Implementation:

1. In `litellm.py`, create a `contextvars.ContextVar`: `_ocw_litellm_active: ContextVar[bool]` (default `False`)
2. In the LiteLLM wrapper, set `_ocw_litellm_active` to `True` before calling the original `litellm.completion`, reset after
3. In `openai.py` and `anthropic.py`, import the context var and check it — if `True`, skip span creation and just call the original function directly

This ensures the outermost patch (LiteLLM) owns the span, and inner provider patches stay silent. The context var changes to `openai.py` and `anthropic.py` are part of this task.

## Scope decisions

- **Async streaming**: YES — wrap both `completion(stream=True)` and `acompletion(stream=True)`. Async is the common path for agent frameworks.
- **`text_completion()`**: NO — legacy API, skip for v1.
- **`Router.completion()`**: NO separate patch needed — Router calls `litellm.completion()` under the hood. Add a test confirming Router produces spans via the top-level patch.

## What NOT to do

- Do NOT patch individual provider calls inside LiteLLM — only patch the top-level `litellm.completion` and `litellm.acompletion`
- Do NOT add LiteLLM as a required dependency — it's optional, like the other framework integrations
- Do NOT duplicate token counting logic — LiteLLM already returns usage in OpenAI format
- Do NOT patch `litellm.text_completion()` — legacy, not worth the surface area

---

## Verification

- `patch_litellm()` works with `litellm.completion("openai/gpt-4o-mini", ...)`
- `patch_litellm()` works with `litellm.completion("anthropic/claude-haiku-4-5", ...)`
- Spans show correct provider attribution from `custom_llm_provider`
- Sync and async streaming work and capture usage
- `Router().completion()` produces a span via the top-level patch
- Double-counting prevention: using both `patch_litellm()` + `patch_openai()` produces exactly one span per call, not two
- All new tests pass
- All 223+ existing tests still pass
- `ruff check ocw/` passes
- Example runs and produces spans visible in `ocw traces`