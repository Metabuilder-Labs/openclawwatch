"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const node_test_1 = require("node:test");
const strict_1 = __importDefault(require("node:assert/strict"));
const node_http_1 = require("node:http");
const client_js_1 = require("./client.js");
const span_builder_js_1 = require("./span-builder.js");
/**
 * Spin up a local HTTP server that captures requests, so we can test
 * the client without a real OCW server.
 */
function createMockServer() {
    const requests = [];
    let responseStatus = 200;
    let responseBody = { ingested: 1, rejected: 0, rejections: [] };
    const server = (0, node_http_1.createServer)((req, res) => {
        let body = "";
        req.on("data", (chunk) => {
            body += chunk.toString();
        });
        req.on("end", () => {
            requests.push({
                method: req.method ?? "",
                url: req.url ?? "",
                headers: req.headers,
                body,
            });
            res.writeHead(responseStatus, { "Content-Type": "application/json" });
            res.end(JSON.stringify(responseBody));
        });
    });
    return {
        server,
        port: () => {
            const addr = server.address();
            if (addr && typeof addr === "object")
                return addr.port;
            throw new Error("Server not started");
        },
        requests,
        setResponse(status, body) {
            responseStatus = status;
            responseBody = body;
        },
        async start() {
            await new Promise((resolve) => {
                server.listen(0, "127.0.0.1", resolve);
            });
        },
        async stop() {
            await new Promise((resolve, reject) => {
                server.close((err) => (err ? reject(err) : resolve()));
            });
        },
    };
}
(0, node_test_1.describe)("OcwClient", () => {
    let mock;
    (0, node_test_1.beforeEach)(async () => {
        mock = createMockServer();
        await mock.start();
    });
    (0, node_test_1.afterEach)(async () => {
        await mock.stop();
    });
    (0, node_test_1.it)("sends a span with correct auth header", async () => {
        const client = new client_js_1.OcwClient({
            baseUrl: `http://127.0.0.1:${mock.port()}`,
            ingestSecret: "test-secret-123",
            batchSize: 1,
        });
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .agentId("test-agent")
            .provider("anthropic")
            .model("claude-haiku-4-5")
            .inputTokens(1000)
            .outputTokens(200)
            .build();
        await client.send(span);
        strict_1.default.equal(mock.requests.length, 1);
        const req = mock.requests[0];
        strict_1.default.equal(req.method, "POST");
        strict_1.default.equal(req.url, "/api/v1/spans");
        strict_1.default.equal(req.headers["authorization"], "Bearer test-secret-123");
        strict_1.default.equal(req.headers["content-type"], "application/json");
    });
    (0, node_test_1.it)("sends OTLP JSON format", async () => {
        const client = new client_js_1.OcwClient({
            baseUrl: `http://127.0.0.1:${mock.port()}`,
            ingestSecret: "secret",
            batchSize: 1,
        });
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .agentId("agent-1")
            .inputTokens(500)
            .build();
        await client.send(span);
        const body = JSON.parse(mock.requests[0].body);
        strict_1.default.ok(body.resourceSpans);
        strict_1.default.ok(Array.isArray(body.resourceSpans));
        strict_1.default.equal(body.resourceSpans.length, 1);
        const scopeSpans = body.resourceSpans[0].scopeSpans;
        strict_1.default.ok(Array.isArray(scopeSpans));
        strict_1.default.equal(scopeSpans[0].spans.length, 1);
        const otlpSpan = scopeSpans[0].spans[0];
        strict_1.default.equal(otlpSpan.name, "gen_ai.llm.call");
        strict_1.default.ok(otlpSpan.traceId);
        strict_1.default.ok(otlpSpan.spanId);
        strict_1.default.equal(otlpSpan.kind, 3); // CLIENT
        strict_1.default.equal(otlpSpan.status.code, 1); // OK
    });
    (0, node_test_1.it)("batches spans and flushes at batchSize", async () => {
        mock.setResponse(200, { ingested: 3, rejected: 0, rejections: [] });
        const client = new client_js_1.OcwClient({
            baseUrl: `http://127.0.0.1:${mock.port()}`,
            ingestSecret: "secret",
            batchSize: 3,
        });
        // Send 2 spans — should not flush yet
        await client.send(new span_builder_js_1.SpanBuilder("span-1").build());
        await client.send(new span_builder_js_1.SpanBuilder("span-2").build());
        strict_1.default.equal(mock.requests.length, 0);
        // Third span triggers flush
        await client.send(new span_builder_js_1.SpanBuilder("span-3").build());
        strict_1.default.equal(mock.requests.length, 1);
        const body = JSON.parse(mock.requests[0].body);
        const spans = body.resourceSpans[0].scopeSpans[0].spans;
        strict_1.default.equal(spans.length, 3);
    });
    (0, node_test_1.it)("flush sends remaining spans", async () => {
        const client = new client_js_1.OcwClient({
            baseUrl: `http://127.0.0.1:${mock.port()}`,
            ingestSecret: "secret",
            batchSize: 100, // won't auto-flush
        });
        await client.send(new span_builder_js_1.SpanBuilder("span-1").build());
        await client.send(new span_builder_js_1.SpanBuilder("span-2").build());
        strict_1.default.equal(mock.requests.length, 0);
        const result = await client.flush();
        strict_1.default.equal(mock.requests.length, 1);
        strict_1.default.ok(result);
        strict_1.default.equal(result.ingested, 1); // mock default
    });
    (0, node_test_1.it)("flush on empty buffer returns null", async () => {
        const client = new client_js_1.OcwClient({
            baseUrl: `http://127.0.0.1:${mock.port()}`,
            ingestSecret: "secret",
        });
        const result = await client.flush();
        strict_1.default.equal(result, null);
        strict_1.default.equal(mock.requests.length, 0);
    });
    (0, node_test_1.it)("shutdown flushes and stops timer", async () => {
        const client = new client_js_1.OcwClient({
            baseUrl: `http://127.0.0.1:${mock.port()}`,
            ingestSecret: "secret",
            batchSize: 100,
            flushIntervalMs: 60000, // won't auto-flush in test
        });
        client.start();
        await client.send(new span_builder_js_1.SpanBuilder("span-1").build());
        await client.shutdown();
        strict_1.default.equal(mock.requests.length, 1);
    });
    (0, node_test_1.it)("throws on server error", async () => {
        mock.setResponse(401, { detail: "Invalid ingest secret" });
        const client = new client_js_1.OcwClient({
            baseUrl: `http://127.0.0.1:${mock.port()}`,
            ingestSecret: "wrong-secret",
            batchSize: 1,
        });
        await strict_1.default.rejects(() => client.send(new span_builder_js_1.SpanBuilder("span-1").build()), (err) => {
            strict_1.default.ok(err.message.includes("401"));
            return true;
        });
    });
    (0, node_test_1.it)("converts span attributes to OTLP format", async () => {
        const client = new client_js_1.OcwClient({
            baseUrl: `http://127.0.0.1:${mock.port()}`,
            ingestSecret: "secret",
            batchSize: 1,
        });
        const span = new span_builder_js_1.SpanBuilder("gen_ai.llm.call")
            .attribute("string.attr", "hello")
            .attribute("int.attr", 42)
            .attribute("float.attr", 3.14)
            .attribute("bool.attr", true)
            .build();
        await client.send(span);
        const body = JSON.parse(mock.requests[0].body);
        const attrs = body.resourceSpans[0].scopeSpans[0].spans[0].attributes;
        const attrMap = new Map(attrs.map((a) => [a.key, a.value]));
        strict_1.default.deepEqual(attrMap.get("string.attr"), { stringValue: "hello" });
        strict_1.default.deepEqual(attrMap.get("int.attr"), { intValue: "42" });
        strict_1.default.deepEqual(attrMap.get("float.attr"), { doubleValue: 3.14 });
        strict_1.default.deepEqual(attrMap.get("bool.attr"), { boolValue: true });
    });
});
//# sourceMappingURL=client.test.js.map