/**
 * Fluent builder for constructing Span objects with GenAI semantic conventions.
 */
import { randomUUID } from "node:crypto";
import { GenAIAttributes } from "./semconv.js";
import { type Span, SpanKind, SpanStatus } from "./types.js";

function newTraceId(): string {
  return randomUUID().replace(/-/g, "");
}

function newSpanId(): string {
  return randomUUID().replace(/-/g, "").slice(0, 16);
}

export class SpanBuilder {
  private span: Span;

  constructor(name: string) {
    const now = new Date().toISOString();
    this.span = {
      spanId: newSpanId(),
      traceId: newTraceId(),
      name,
      kind: SpanKind.CLIENT,
      statusCode: SpanStatus.OK,
      startTime: now,
      attributes: {},
    };
  }

  traceId(id: string): this {
    this.span.traceId = id;
    return this;
  }

  spanId(id: string): this {
    this.span.spanId = id;
    return this;
  }

  parentSpanId(id: string): this {
    this.span.parentSpanId = id;
    return this;
  }

  kind(kind: SpanKind): this {
    this.span.kind = kind;
    return this;
  }

  status(code: SpanStatus, message?: string): this {
    this.span.statusCode = code;
    if (message) this.span.statusMessage = message;
    return this;
  }

  startTime(iso: string): this {
    this.span.startTime = iso;
    return this;
  }

  endTime(iso: string): this {
    this.span.endTime = iso;
    return this;
  }

  durationMs(ms: number): this {
    this.span.durationMs = ms;
    return this;
  }

  agentId(id: string): this {
    this.span.agentId = id;
    this.span.attributes[GenAIAttributes.AGENT_ID] = id;
    return this;
  }

  sessionId(id: string): this {
    this.span.sessionId = id;
    this.span.attributes["gen_ai.session.id"] = id;
    return this;
  }

  conversationId(id: string): this {
    this.span.conversationId = id;
    this.span.attributes[GenAIAttributes.CONVERSATION_ID] = id;
    return this;
  }

  provider(name: string): this {
    this.span.attributes[GenAIAttributes.PROVIDER_NAME] = name;
    return this;
  }

  model(name: string): this {
    this.span.attributes[GenAIAttributes.REQUEST_MODEL] = name;
    return this;
  }

  inputTokens(n: number): this {
    this.span.attributes[GenAIAttributes.INPUT_TOKENS] = n;
    return this;
  }

  outputTokens(n: number): this {
    this.span.attributes[GenAIAttributes.OUTPUT_TOKENS] = n;
    return this;
  }

  cacheReadTokens(n: number): this {
    this.span.attributes[GenAIAttributes.CACHE_READ_TOKENS] = n;
    return this;
  }

  toolName(name: string): this {
    this.span.attributes[GenAIAttributes.TOOL_NAME] = name;
    return this;
  }

  toolInput(input: string): this {
    this.span.attributes[GenAIAttributes.TOOL_INPUT] = input;
    return this;
  }

  toolOutput(output: string): this {
    this.span.attributes[GenAIAttributes.TOOL_OUTPUT] = output;
    return this;
  }

  attribute(key: string, value: unknown): this {
    this.span.attributes[key] = value;
    return this;
  }

  build(): Span {
    const endTime = (!this.span.endTime && this.span.durationMs != null)
      ? new Date(new Date(this.span.startTime).getTime() + this.span.durationMs).toISOString()
      : this.span.endTime;
    return { ...this.span, endTime, attributes: { ...this.span.attributes } };
  }
}
