import type { IngestResult, Span } from "./types.js";
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
export declare class OcwClient {
    private readonly baseUrl;
    private readonly ingestSecret;
    private readonly batchSize;
    private readonly flushIntervalMs;
    private buffer;
    private timer;
    constructor(options: OcwClientOptions);
    /**
     * Start the automatic flush timer.
     * Call this once after creating the client.
     */
    start(): this;
    /**
     * Add a span to the buffer. Auto-flushes when batchSize is reached.
     */
    send(span: Span): Promise<void>;
    /**
     * Flush all buffered spans to the server.
     * Returns the ingest result, or null if the buffer was empty.
     */
    flush(): Promise<IngestResult | null>;
    /**
     * Flush remaining spans and stop the timer.
     */
    shutdown(): Promise<void>;
    /**
     * Convert SDK spans to OTLP JSON batch format.
     */
    private toBatch;
    /**
     * POST a span batch to the ingest endpoint.
     */
    private post;
}
