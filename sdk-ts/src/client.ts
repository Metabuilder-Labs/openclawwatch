/**
 * OcwClient — sends spans to the OCW REST API.
 * Communicates via HTTP POST to /api/v1/spans in OTLP JSON format.
 */
import { GenAIAttributes } from "./semconv.js";
import type { IngestResult, OtlpSpan, OtlpValue, Span, SpanBatch } from "./types.js";
import { SpanKind, SpanStatus } from "./types.js";

export interface OcwClientOptions {
  /** Base URL of the OCW server (default: http://127.0.0.1:7391) */
  baseUrl?: string;
  /** Ingest secret for authentication */
  ingestSecret: string;
  /** Maximum batch size before auto-flush (default: 50) */
  batchSize?: number;
  /** Flush interval in milliseconds (default: 5000) */
  flushIntervalMs?: number;
}

const SPAN_KIND_TO_OTLP: Record<string, number> = {
  [SpanKind.INTERNAL]: 1,
  [SpanKind.SERVER]: 2,
  [SpanKind.CLIENT]: 3,
  [SpanKind.PRODUCER]: 4,
  [SpanKind.CONSUMER]: 5,
};

const STATUS_CODE_TO_OTLP: Record<string, number> = {
  [SpanStatus.UNSET]: 0,
  [SpanStatus.OK]: 1,
  [SpanStatus.ERROR]: 2,
};

function isoToUnixNano(iso: string): string {
  const ms = new Date(iso).getTime();
  // Represent as nanoseconds in a string (BigInt-safe)
  return `${ms}000000`;
}

function toOtlpValue(value: unknown): OtlpValue {
  if (typeof value === "string") return { stringValue: value };
  if (typeof value === "number") {
    if (Number.isInteger(value)) return { intValue: String(value) };
    return { doubleValue: value };
  }
  if (typeof value === "boolean") return { boolValue: value };
  if (Array.isArray(value)) {
    return { arrayValue: { values: value.map(toOtlpValue) } };
  }
  return { stringValue: String(value) };
}

function spanToOtlp(span: Span): OtlpSpan {
  const attributes = Object.entries(span.attributes).map(([key, value]) => ({
    key,
    value: toOtlpValue(value),
  }));

  const otlp: OtlpSpan = {
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

  if (span.parentSpanId) otlp.parentSpanId = span.parentSpanId;
  if (span.endTime) otlp.endTimeUnixNano = isoToUnixNano(span.endTime);

  return otlp;
}

export class OcwClient {
  private readonly baseUrl: string;
  private readonly ingestSecret: string;
  private readonly batchSize: number;
  private readonly flushIntervalMs: number;
  private buffer: Span[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(options: OcwClientOptions) {
    this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:7391").replace(
      /\/$/,
      ""
    );
    this.ingestSecret = options.ingestSecret;
    this.batchSize = options.batchSize ?? 50;
    this.flushIntervalMs = options.flushIntervalMs ?? 5000;
  }

  /**
   * Start the automatic flush timer.
   * Call this once after creating the client.
   */
  start(): this {
    if (this.timer) return this;
    this.timer = setInterval(() => {
      void this.flush();
    }, this.flushIntervalMs);
    // Allow process to exit even if timer is running
    if (this.timer.unref) this.timer.unref();
    return this;
  }

  /**
   * Add a span to the buffer. Auto-flushes when batchSize is reached.
   */
  async send(span: Span): Promise<void> {
    this.buffer.push(span);
    if (this.buffer.length >= this.batchSize) {
      await this.flush();
    }
  }

  /**
   * Flush all buffered spans to the server.
   * Returns the ingest result, or null if the buffer was empty.
   */
  async flush(): Promise<IngestResult | null> {
    if (this.buffer.length === 0) return null;

    const spans = this.buffer.splice(0);
    const batch = this.toBatch(spans);
    return this.post(batch);
  }

  /**
   * Flush remaining spans and stop the timer.
   */
  async shutdown(): Promise<void> {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    await this.flush();
  }

  /**
   * Convert SDK spans to OTLP JSON batch format.
   */
  private toBatch(spans: Span[]): SpanBatch {
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
  private async post(batch: SpanBatch): Promise<IngestResult> {
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
      throw new Error(
        `OCW ingest failed: ${response.status} ${response.statusText} — ${text}`
      );
    }

    return (await response.json()) as IngestResult;
  }
}
