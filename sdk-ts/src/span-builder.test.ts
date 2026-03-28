import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { SpanBuilder } from "./span-builder.js";
import { SpanKind, SpanStatus } from "./types.js";
import { GenAIAttributes } from "./semconv.js";

describe("SpanBuilder", () => {
  it("creates a span with required fields", () => {
    const span = new SpanBuilder("gen_ai.llm.call").build();
    assert.ok(span.spanId);
    assert.ok(span.traceId);
    assert.equal(span.name, "gen_ai.llm.call");
    assert.equal(span.kind, SpanKind.CLIENT);
    assert.equal(span.statusCode, SpanStatus.OK);
    assert.ok(span.startTime);
  });

  it("sets agent and provider attributes", () => {
    const span = new SpanBuilder("gen_ai.llm.call")
      .agentId("my-agent")
      .provider("anthropic")
      .model("claude-haiku-4-5")
      .build();

    assert.equal(span.agentId, "my-agent");
    assert.equal(span.attributes[GenAIAttributes.AGENT_ID], "my-agent");
    assert.equal(span.attributes[GenAIAttributes.PROVIDER_NAME], "anthropic");
    assert.equal(span.attributes[GenAIAttributes.REQUEST_MODEL], "claude-haiku-4-5");
  });

  it("sets token counts", () => {
    const span = new SpanBuilder("gen_ai.llm.call")
      .inputTokens(1000)
      .outputTokens(200)
      .cacheReadTokens(500)
      .build();

    assert.equal(span.attributes[GenAIAttributes.INPUT_TOKENS], 1000);
    assert.equal(span.attributes[GenAIAttributes.OUTPUT_TOKENS], 200);
    assert.equal(span.attributes[GenAIAttributes.CACHE_READ_TOKENS], 500);
  });

  it("sets tool call attributes", () => {
    const span = new SpanBuilder("gen_ai.tool.call")
      .kind(SpanKind.INTERNAL)
      .toolName("search")
      .toolInput('{"query": "test"}')
      .toolOutput('{"results": []}')
      .build();

    assert.equal(span.kind, SpanKind.INTERNAL);
    assert.equal(span.attributes[GenAIAttributes.TOOL_NAME], "search");
    assert.equal(span.attributes[GenAIAttributes.TOOL_INPUT], '{"query": "test"}');
    assert.equal(span.attributes[GenAIAttributes.TOOL_OUTPUT], '{"results": []}');
  });

  it("sets conversation and session IDs", () => {
    const span = new SpanBuilder("gen_ai.llm.call")
      .conversationId("conv-123")
      .sessionId("sess-456")
      .build();

    assert.equal(span.conversationId, "conv-123");
    assert.equal(span.sessionId, "sess-456");
    assert.equal(span.attributes[GenAIAttributes.CONVERSATION_ID], "conv-123");
  });

  it("calculates endTime from durationMs", () => {
    const start = "2026-03-28T10:00:00.000Z";
    const span = new SpanBuilder("gen_ai.llm.call")
      .startTime(start)
      .durationMs(500)
      .build();

    assert.equal(span.endTime, "2026-03-28T10:00:00.500Z");
  });

  it("sets custom attributes", () => {
    const span = new SpanBuilder("gen_ai.llm.call")
      .attribute("custom.key", "custom-value")
      .attribute("custom.number", 42)
      .build();

    assert.equal(span.attributes["custom.key"], "custom-value");
    assert.equal(span.attributes["custom.number"], 42);
  });

  it("sets error status", () => {
    const span = new SpanBuilder("gen_ai.llm.call")
      .status(SpanStatus.ERROR, "rate limited")
      .build();

    assert.equal(span.statusCode, SpanStatus.ERROR);
    assert.equal(span.statusMessage, "rate limited");
  });

  it("sets parent span ID and trace ID", () => {
    const span = new SpanBuilder("gen_ai.llm.call")
      .traceId("aabbccdd00112233aabbccdd00112233")
      .parentSpanId("1122334455667788")
      .build();

    assert.equal(span.traceId, "aabbccdd00112233aabbccdd00112233");
    assert.equal(span.parentSpanId, "1122334455667788");
  });

  it("returns a copy on build (immutable)", () => {
    const builder = new SpanBuilder("gen_ai.llm.call").agentId("agent-1");
    const span1 = builder.build();
    const span2 = builder.agentId("agent-2").build();

    assert.equal(span1.agentId, "agent-1");
    assert.equal(span2.agentId, "agent-2");
    // Attributes should be independent copies
    assert.equal(span1.attributes[GenAIAttributes.AGENT_ID], "agent-1");
  });
});
