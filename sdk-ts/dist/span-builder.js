"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SpanBuilder = void 0;
/**
 * Fluent builder for constructing Span objects with GenAI semantic conventions.
 */
const node_crypto_1 = require("node:crypto");
const semconv_js_1 = require("./semconv.js");
const types_js_1 = require("./types.js");
function newTraceId() {
    return (0, node_crypto_1.randomUUID)().replace(/-/g, "");
}
function newSpanId() {
    return (0, node_crypto_1.randomUUID)().replace(/-/g, "").slice(0, 16);
}
class SpanBuilder {
    span;
    constructor(name) {
        const now = new Date().toISOString();
        this.span = {
            spanId: newSpanId(),
            traceId: newTraceId(),
            name,
            kind: types_js_1.SpanKind.CLIENT,
            statusCode: types_js_1.SpanStatus.OK,
            startTime: now,
            attributes: {},
        };
    }
    traceId(id) {
        this.span.traceId = id;
        return this;
    }
    spanId(id) {
        this.span.spanId = id;
        return this;
    }
    parentSpanId(id) {
        this.span.parentSpanId = id;
        return this;
    }
    kind(kind) {
        this.span.kind = kind;
        return this;
    }
    status(code, message) {
        this.span.statusCode = code;
        if (message)
            this.span.statusMessage = message;
        return this;
    }
    startTime(iso) {
        this.span.startTime = iso;
        return this;
    }
    endTime(iso) {
        this.span.endTime = iso;
        return this;
    }
    durationMs(ms) {
        this.span.durationMs = ms;
        return this;
    }
    agentId(id) {
        this.span.agentId = id;
        this.span.attributes[semconv_js_1.GenAIAttributes.AGENT_ID] = id;
        return this;
    }
    sessionId(id) {
        this.span.sessionId = id;
        return this;
    }
    conversationId(id) {
        this.span.conversationId = id;
        this.span.attributes[semconv_js_1.GenAIAttributes.CONVERSATION_ID] = id;
        return this;
    }
    provider(name) {
        this.span.attributes[semconv_js_1.GenAIAttributes.PROVIDER_NAME] = name;
        return this;
    }
    model(name) {
        this.span.attributes[semconv_js_1.GenAIAttributes.REQUEST_MODEL] = name;
        return this;
    }
    inputTokens(n) {
        this.span.attributes[semconv_js_1.GenAIAttributes.INPUT_TOKENS] = n;
        return this;
    }
    outputTokens(n) {
        this.span.attributes[semconv_js_1.GenAIAttributes.OUTPUT_TOKENS] = n;
        return this;
    }
    cacheReadTokens(n) {
        this.span.attributes[semconv_js_1.GenAIAttributes.CACHE_READ_TOKENS] = n;
        return this;
    }
    toolName(name) {
        this.span.attributes[semconv_js_1.GenAIAttributes.TOOL_NAME] = name;
        return this;
    }
    toolInput(input) {
        this.span.attributes[semconv_js_1.GenAIAttributes.TOOL_INPUT] = input;
        return this;
    }
    toolOutput(output) {
        this.span.attributes[semconv_js_1.GenAIAttributes.TOOL_OUTPUT] = output;
        return this;
    }
    attribute(key, value) {
        this.span.attributes[key] = value;
        return this;
    }
    build() {
        if (!this.span.endTime && this.span.durationMs != null) {
            const start = new Date(this.span.startTime).getTime();
            this.span.endTime = new Date(start + this.span.durationMs).toISOString();
        }
        return { ...this.span, attributes: { ...this.span.attributes } };
    }
}
exports.SpanBuilder = SpanBuilder;
//# sourceMappingURL=span-builder.js.map