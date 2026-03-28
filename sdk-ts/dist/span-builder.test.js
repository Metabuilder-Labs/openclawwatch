"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const node_test_1 = require("node:test");
const strict_1 = __importDefault(require("node:assert/strict"));
const span_builder_js_1 = require("./span-builder.js");
const types_js_1 = require("./types.js");
const semconv_js_1 = require("./semconv.js");
(0, node_test_1.describe)("SpanBuilder", () => {
    (0, node_test_1.it)("creates a span with required fields", () => {
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call").build();
        strict_1.default.ok(span.spanId);
        strict_1.default.ok(span.traceId);
        strict_1.default.equal(span.name, "gen_ai.llm.call");
        strict_1.default.equal(span.kind, types_js_1.SpanKind.CLIENT);
        strict_1.default.equal(span.statusCode, types_js_1.SpanStatus.OK);
        strict_1.default.ok(span.startTime);
    });
    (0, node_test_1.it)("sets agent and provider attributes", () => {
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .agentId("my-agent")
            .provider("anthropic")
            .model("claude-haiku-4-5")
            .build();
        strict_1.default.equal(span.agentId, "my-agent");
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.AGENT_ID], "my-agent");
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.PROVIDER_NAME], "anthropic");
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.REQUEST_MODEL], "claude-haiku-4-5");
    });
    (0, node_test_1.it)("sets token counts", () => {
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .inputTokens(1000)
            .outputTokens(200)
            .cacheReadTokens(500)
            .build();
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.INPUT_TOKENS], 1000);
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.OUTPUT_TOKENS], 200);
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.CACHE_READ_TOKENS], 500);
    });
    (0, node_test_1.it)("sets tool call attributes", () => {
        const span = new span_builder_js_1.SpanBuilder("gen_ai.tool.call")
            .kind(types_js_1.SpanKind.INTERNAL)
            .toolName("search")
            .toolInput('{"query": "test"}')
            .toolOutput('{"results": []}')
            .build();
        strict_1.default.equal(span.kind, types_js_1.SpanKind.INTERNAL);
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.TOOL_NAME], "search");
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.TOOL_INPUT], '{"query": "test"}');
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.TOOL_OUTPUT], '{"results": []}');
    });
    (0, node_test_1.it)("sets conversation and session IDs", () => {
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .conversationId("conv-123")
            .sessionId("sess-456")
            .build();
        strict_1.default.equal(span.conversationId, "conv-123");
        strict_1.default.equal(span.sessionId, "sess-456");
        strict_1.default.equal(span.attributes[semconv_js_1.GenAIAttributes.CONVERSATION_ID], "conv-123");
    });
    (0, node_test_1.it)("calculates endTime from durationMs", () => {
        const start = "2026-03-28T10:00:00.000Z";
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .startTime(start)
            .durationMs(500)
            .build();
        strict_1.default.equal(span.endTime, "2026-03-28T10:00:00.500Z");
    });
    (0, node_test_1.it)("sets custom attributes", () => {
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .attribute("custom.key", "custom-value")
            .attribute("custom.number", 42)
            .build();
        strict_1.default.equal(span.attributes["custom.key"], "custom-value");
        strict_1.default.equal(span.attributes["custom.number"], 42);
    });
    (0, node_test_1.it)("sets error status", () => {
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .status(types_js_1.SpanStatus.ERROR, "rate limited")
            .build();
        strict_1.default.equal(span.statusCode, types_js_1.SpanStatus.ERROR);
        strict_1.default.equal(span.statusMessage, "rate limited");
    });
    (0, node_test_1.it)("sets parent span ID and trace ID", () => {
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .traceId("aabbccdd00112233aabbccdd00112233")
            .parentSpanId("1122334455667788")
            .build();
        strict_1.default.equal(span.traceId, "aabbccdd00112233aabbccdd00112233");
        strict_1.default.equal(span.parentSpanId, "1122334455667788");
    });
    (0, node_test_1.it)("returns a copy on build (immutable)", () => {
        const builder = new span_builder_js_1.SpanBuilder("gen_ai.llm.call").agentId("agent-1");
        const span1 = builder.build();
        const span2 = builder.agentId("agent-2").build();
        strict_1.default.equal(span1.agentId, "agent-1");
        strict_1.default.equal(span2.agentId, "agent-2");
        // Attributes should be independent copies
        strict_1.default.equal(span1.attributes[semconv_js_1.GenAIAttributes.AGENT_ID], "agent-1");
    });
});
//# sourceMappingURL=span-builder.test.js.map