"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OcwClient = void 0;
const types_js_1 = require("./types.js");
const SPAN_KIND_TO_OTLP = {
    [types_js_1.SpanKind.INTERNAL]: 1,
    [types_js_1.SpanKind.SERVER]: 2,
    [types_js_1.SpanKind.CLIENT]: 3,
    [types_js_1.SpanKind.PRODUCER]: 4,
    [types_js_1.SpanKind.CONSUMER]: 5,
};
const STATUS_CODE_TO_OTLP = {
    [types_js_1.SpanStatus.UNSET]: 0,
    [types_js_1.SpanStatus.OK]: 1,
    [types_js_1.SpanStatus.ERROR]: 2,
};
function isoToUnixNano(iso) {
    const ms = new Date(iso).getTime();
    // Represent as nanoseconds in a string (BigInt-safe)
    return `${ms}000000`;
}
function toOtlpValue(value) {
    if (typeof value === "string")
        return { stringValue: value };
    if (typeof value === "number") {
        if (Number.isInteger(value))
            return { intValue: String(value) };
        return { doubleValue: value };
    }
    if (typeof value === "boolean")
        return { boolValue: value };
    if (Array.isArray(value)) {
        return { arrayValue: { values: value.map(toOtlpValue) } };
    }
    return { stringValue: String(value) };
}
function spanToOtlp(span) {
    const attributes = Object.entries(span.attributes).map(([key, value]) => ({
        key,
        value: toOtlpValue(value),
    }));
    const otlp = {
        traceId: span.traceId,
        spanId: span.spanId,
        name: span.name,
        kind: SPAN_KIND_TO_OTLP[span.kind] ?? 1,
        startTimeUnixNano: isoToUnixNano(span.startTime),
        status: {
            code: STATUS_CODE_TO_OTLP[span.statusCode] ?? 0,
            message: span.statusMessage,
        },
        attributes,
    };
    if (span.parentSpanId)
        otlp.parentSpanId = span.parentSpanId;
    if (span.endTime)
        otlp.endTimeUnixNano = isoToUnixNano(span.endTime);
    return otlp;
}
class OcwClient {
    baseUrl;
    ingestSecret;
    batchSize;
    flushIntervalMs;
    buffer = [];
    timer = null;
    constructor(options) {
        this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:7391").replace(/\/$/, "");
        this.ingestSecret = options.ingestSecret;
        this.batchSize = options.batchSize ?? 50;
        this.flushIntervalMs = options.flushIntervalMs ?? 5000;
    }
    /**
     * Start the automatic flush timer.
     * Call this once after creating the client.
     */
    start() {
        if (this.timer)
            return this;
        this.timer = setInterval(() => {
            void this.flush();
        }, this.flushIntervalMs);
        // Allow process to exit even if timer is running
        if (this.timer.unref)
            this.timer.unref();
        return this;
    }
    /**
     * Add a span to the buffer. Auto-flushes when batchSize is reached.
     */
    async send(span) {
        this.buffer.push(span);
        if (this.buffer.length >= this.batchSize) {
            await this.flush();
        }
    }
    /**
     * Flush all buffered spans to the server.
     * Returns the ingest result, or null if the buffer was empty.
     */
    async flush() {
        if (this.buffer.length === 0)
            return null;
        const spans = this.buffer.splice(0);
        const batch = this.toBatch(spans);
        return this.post(batch);
    }
    /**
     * Flush remaining spans and stop the timer.
     */
    async shutdown() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        await this.flush();
    }
    /**
     * Convert SDK spans to OTLP JSON batch format.
     */
    toBatch(spans) {
        return {
            resourceSpans: [
                {
                    resource: {
                        attributes: [
                            {
                                key: "service.name",
                                value: { stringValue: "ocw-ts-sdk" },
                            },
                        ],
                    },
                    scopeSpans: [
                        {
                            spans: spans.map(spanToOtlp),
                        },
                    ],
                },
            ],
        };
    }
    /**
     * POST a span batch to the ingest endpoint.
     */
    async post(batch) {
        const url = `${this.baseUrl}/api/v1/spans`;
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${this.ingestSecret}`,
            },
            body: JSON.stringify(batch),
        });
        if (!response.ok) {
            const text = await response.text().catch(() => "");
            throw new Error(`OCW ingest failed: ${response.status} ${response.statusText} — ${text}`);
        }
        return (await response.json());
    }
}
exports.OcwClient = OcwClient;
//# sourceMappingURL=client.js.map