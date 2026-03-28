import { type Span, SpanKind, SpanStatus } from "./types.js";
export declare class SpanBuilder {
    private span;
    constructor(name: string);
    traceId(id: string): this;
    spanId(id: string): this;
    parentSpanId(id: string): this;
    kind(kind: SpanKind): this;
    status(code: SpanStatus, message?: string): this;
    startTime(iso: string): this;
    endTime(iso: string): this;
    durationMs(ms: number): this;
    agentId(id: string): this;
    sessionId(id: string): this;
    conversationId(id: string): this;
    provider(name: string): this;
    model(name: string): this;
    inputTokens(n: number): this;
    outputTokens(n: number): this;
    cacheReadTokens(n: number): this;
    toolName(name: string): this;
    toolInput(input: string): this;
    toolOutput(output: string): this;
    attribute(key: string, value: unknown): this;
    build(): Span;
}
