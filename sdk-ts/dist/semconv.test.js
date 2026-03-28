"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const node_test_1 = require("node:test");
const strict_1 = __importDefault(require("node:assert/strict"));
const semconv_js_1 = require("./semconv.js");
(0, node_test_1.describe)("GenAIAttributes", () => {
    (0, node_test_1.it)("has standard GenAI attribute keys", () => {
        strict_1.default.equal(semconv_js_1.GenAIAttributes.AGENT_ID, "gen_ai.agent.id");
        strict_1.default.equal(semconv_js_1.GenAIAttributes.PROVIDER_NAME, "gen_ai.provider.name");
        strict_1.default.equal(semconv_js_1.GenAIAttributes.REQUEST_MODEL, "gen_ai.request.model");
        strict_1.default.equal(semconv_js_1.GenAIAttributes.INPUT_TOKENS, "gen_ai.usage.input_tokens");
        strict_1.default.equal(semconv_js_1.GenAIAttributes.OUTPUT_TOKENS, "gen_ai.usage.output_tokens");
        strict_1.default.equal(semconv_js_1.GenAIAttributes.TOOL_NAME, "gen_ai.tool.name");
        strict_1.default.equal(semconv_js_1.GenAIAttributes.CONVERSATION_ID, "gen_ai.conversation.id");
    });
    (0, node_test_1.it)("has standard span names", () => {
        strict_1.default.equal(semconv_js_1.GenAIAttributes.SPAN_LLM_CALL, "gen_ai.llm.call");
        strict_1.default.equal(semconv_js_1.GenAIAttributes.SPAN_TOOL_CALL, "gen_ai.tool.call");
        strict_1.default.equal(semconv_js_1.GenAIAttributes.SPAN_INVOKE_AGENT, "invoke_agent");
    });
});
(0, node_test_1.describe)("OcwAttributes", () => {
    (0, node_test_1.it)("has ocw-specific attribute keys", () => {
        strict_1.default.equal(semconv_js_1.OcwAttributes.COST_USD, "ocw.cost_usd");
        strict_1.default.equal(semconv_js_1.OcwAttributes.ALERT_TYPE, "ocw.alert.type");
        strict_1.default.equal(semconv_js_1.OcwAttributes.SANDBOX_EVENT, "ocw.sandbox.event");
    });
});
//# sourceMappingURL=semconv.test.js.map