import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { GenAIAttributes, OcwAttributes } from "./semconv.js";

describe("GenAIAttributes", () => {
  it("has standard GenAI attribute keys", () => {
    assert.equal(GenAIAttributes.AGENT_ID, "gen_ai.agent.id");
    assert.equal(GenAIAttributes.PROVIDER_NAME, "gen_ai.provider.name");
    assert.equal(GenAIAttributes.REQUEST_MODEL, "gen_ai.request.model");
    assert.equal(GenAIAttributes.INPUT_TOKENS, "gen_ai.usage.input_tokens");
    assert.equal(GenAIAttributes.OUTPUT_TOKENS, "gen_ai.usage.output_tokens");
    assert.equal(GenAIAttributes.TOOL_NAME, "gen_ai.tool.name");
    assert.equal(GenAIAttributes.CONVERSATION_ID, "gen_ai.conversation.id");
  });

  it("has standard span names", () => {
    assert.equal(GenAIAttributes.SPAN_LLM_CALL, "gen_ai.llm.call");
    assert.equal(GenAIAttributes.SPAN_TOOL_CALL, "gen_ai.tool.call");
    assert.equal(GenAIAttributes.SPAN_INVOKE_AGENT, "invoke_agent");
  });
});

describe("OcwAttributes", () => {
  it("has ocw-specific attribute keys", () => {
    assert.equal(OcwAttributes.COST_USD, "ocw.cost_usd");
    assert.equal(OcwAttributes.ALERT_TYPE, "ocw.alert.type");
    assert.equal(OcwAttributes.SANDBOX_EVENT, "ocw.sandbox.event");
  });
});
