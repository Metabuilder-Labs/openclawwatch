# Task 10 — TypeScript SDK
**Depends on:** Task 00 (foundation — semconv constants for reference).
**Parallel with:** All other tasks.
**Estimated scope:** Medium. Fully independent of all Python tasks.

---

## What this task covers

The `@ocw/sdk` TypeScript package under `sdk-ts/`. This is a completely standalone
package — it does not share code with the Python package. It communicates with the
Python backend via HTTP only.

---

## Package setup

### `sdk-ts/package.json`

```json
{
  "name": "@ocw/sdk",
  "version": "0.1.0",
  "description": "TypeScript SDK for OpenClawWatch",
  "main": "./dist/index.js",
  "module": "./dist/index.mjs",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.js",
      "types": "./dist/index.d.ts"
    }
  },
  "scripts": {
    "build": "tsdown",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {},
  "devDependencies": {
    "typescript": "^5.4",
    "tsdown": "^0.1",
    "vitest": "^1.0",
    "@types/node": "^20"
  }
}
```

### `sdk-ts/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "declaration": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src"]
}
```

---

## Deliverables

### `sdk-ts/src/semconv.ts`

TypeScript mirror of the Python `GenAIAttributes` constants. Keep in sync with
`ocw/otel/semconv.py` — the attribute names must match exactly.

```typescript
export const GenAIAttributes = {
  AGENT_ID:           "gen_ai.agent.id",
  AGENT_NAME:         "gen_ai.agent.name",
  AGENT_VERSION:      "gen_ai.agent.version",
  PROVIDER_NAME:      "gen_ai.provider.name",
  REQUEST_MODEL:      "gen_ai.request.model",
  INPUT_TOKENS:       "gen_ai.usage.input_tokens",
  OUTPUT_TOKENS:      "gen_ai.usage.output_tokens",
  CACHE_READ_TOKENS:  "gen_ai.usage.cache_read_tokens",
  TOOL_NAME:          "gen_ai.tool.name",
  TOOL_INPUT:         "gen_ai.tool.input",
  TOOL_OUTPUT:        "gen_ai.tool.output",
  CONVERSATION_ID:    "gen_ai.conversation.id",
  SPAN_INVOKE_AGENT:  "invoke_agent",
  SPAN_TOOL_CALL:     "gen_ai.tool.call",
  SPAN_LLM_CALL:      "gen_ai.llm.call",
} as const;
```

---

### `sdk-ts/src/transport.ts`

HTTP transport to `POST /api/v1/spans`. The only communication channel
between the TS SDK and the Python backend.

```typescript
export interface OcwSpan {
  spanId:          string;
  traceId:         string;
  parentSpanId?:   string;
  name:            string;
  startTimeMs:     number;
  endTimeMs?:      number;
  durationMs?:     number;
  statusCode:      "ok" | "error" | "unset";
  attributes:      Record<string, unknown>;
  agentId?:        string;
  conversationId?: string;
}

export interface TransportConfig {
  baseUrl:       string;   // e.g. "http://127.0.0.1:7391"
  ingestSecret:  string;
  bufferSize?:   number;   // default 1000
  retries?:      number;   // default 3
}

export class HttpTransport {
  private buffer: OcwSpan[] = [];
  private maxBuffer: number;

  constructor(private config: TransportConfig) {
    this.maxBuffer = config.bufferSize ?? 1000;
  }

  async flush(spans: OcwSpan[]): Promise<boolean> {
    /**
     * POST spans to /api/v1/spans.
     * Returns true on success.
     * On failure: buffers spans (up to maxBuffer), returns false.
     * Retries with exponential backoff (base 2s, max 3 attempts).
     */
    ...
  }

  getBuffered(): OcwSpan[] { return [...this.buffer]; }
  clearBuffer(): void { this.buffer = []; }
}
```

---

### `sdk-ts/src/agent.ts`

```typescript
import { randomUUID } from "crypto";
import { GenAIAttributes } from "./semconv.js";
import { HttpTransport, OcwSpan } from "./transport.js";

export interface WatchOptions {
  agentId:        string;
  agentName?:     string;
  agentVersion?:  string;
  conversationId?: string;
  transport:      HttpTransport;
}

/**
 * Wraps an async agent function with session tracking.
 *
 * Creates a span named "invoke_agent" with gen_ai.agent.id set.
 * Records start time, end time, duration, and success/error status.
 *
 * IMPORTANT: This wrapper tracks the session only. Individual LLM call
 * spans require calling recordLlmCall() manually or using a provider patch.
 *
 * Never throws — if something goes wrong with span recording, the agent
 * function still runs normally.
 */
export function watch<T>(
  fn: (...args: unknown[]) => Promise<T>,
  options: WatchOptions,
): (...args: unknown[]) => Promise<T> {
  return async (...args) => {
    const span = startSessionSpan(options);
    try {
      const result = await fn(...args);
      span.statusCode = "ok";
      return result;
    } catch (err) {
      span.statusCode = "error";
      throw err;
    } finally {
      span.endTimeMs  = Date.now();
      span.durationMs = span.endTimeMs - span.startTimeMs;
      await options.transport.flush([span]);
    }
  };
}

function startSessionSpan(options: WatchOptions): OcwSpan {
  const span: OcwSpan = {
    spanId:    randomUUID().replace(/-/g, "").slice(0, 16),
    traceId:   randomUUID().replace(/-/g, ""),
    name:      GenAIAttributes.SPAN_INVOKE_AGENT,
    startTimeMs: Date.now(),
    statusCode: "unset",
    attributes: {
      [GenAIAttributes.AGENT_ID]: options.agentId,
    },
    agentId:        options.agentId,
    conversationId: options.conversationId ?? randomUUID(),
  };
  if (options.agentName) {
    span.attributes[GenAIAttributes.AGENT_NAME] = options.agentName;
  }
  if (options.agentVersion) {
    span.attributes[GenAIAttributes.AGENT_VERSION] = options.agentVersion;
  }
  if (span.conversationId) {
    span.attributes[GenAIAttributes.CONVERSATION_ID] = span.conversationId;
  }
  return span;
}

export async function recordLlmCall(
  transport: HttpTransport,
  options: {
    model:        string;
    provider:     string;
    inputTokens:  number;
    outputTokens: number;
    cacheReadTokens?: number;
    durationMs?:  number;
    agentId?:     string;
    traceId?:     string;
    conversationId?: string;
  }
): Promise<void> {
  /**
   * Manual instrumentation: record a single LLM call span.
   * Use when no provider patch is available.
   */
  ...
}

export async function recordToolCall(
  transport: HttpTransport,
  options: {
    toolName:   string;
    durationMs?: number;
    status?:    "ok" | "error";
    agentId?:   string;
    traceId?:   string;
    conversationId?: string;
  }
): Promise<void> {
  ...
}
```

---

### `sdk-ts/src/integrations/langchain.ts`

Wraps LangChain JS `BaseLLM.generate` and `BaseTool.invoke`.
Same pattern as Python — patch base class methods at import time.

```typescript
export function patchLangChain(transport: HttpTransport): void { ... }
```

---

### `sdk-ts/src/integrations/openai.ts`

Wraps `openai.chat.completions.create`. Also works for OpenAI-compatible
providers (Groq, Together, xAI, Azure OpenAI) via custom `baseURL`.

```typescript
export function patchOpenAI(transport: HttpTransport, baseUrl?: string): void { ... }
```

---

### `sdk-ts/src/index.ts`

```typescript
export { watch, recordLlmCall, recordToolCall } from "./agent.js";
export { HttpTransport }                         from "./transport.js";
export { GenAIAttributes }                       from "./semconv.js";
export { patchLangChain }                        from "./integrations/langchain.js";
export { patchOpenAI }                           from "./integrations/openai.js";
```

---

## Usage example

```typescript
import { watch, recordLlmCall, patchOpenAI, HttpTransport } from "@ocw/sdk";

const transport = new HttpTransport({
  baseUrl:      "http://127.0.0.1:7391",
  ingestSecret: process.env.OCW_INGEST_SECRET ?? "",
});

patchOpenAI(transport);   // auto-records all openai.chat.completions.create() calls

const runAgent = watch(
  async (task: string) => {
    const completion = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: task }],
    });
    return completion.choices[0].message.content;
  },
  { agentId: "my-ts-agent", transport }
);

await runAgent("Summarise these emails");
```

---

## Tests to write

**`sdk-ts/src/__tests__/transport.test.ts`** (Vitest):

```typescript
describe("HttpTransport", () => {
  it("posts spans to /api/v1/spans with correct auth header")
  it("buffers spans when server unreachable")
  it("returns false on connection refused")
  it("does not exceed buffer size limit")
  it("retries on 5xx with exponential backoff")
  it("does not retry on 401")
})
```

**`sdk-ts/src/__tests__/agent.test.ts`**:

```typescript
describe("watch", () => {
  it("creates an invoke_agent span on entry")
  it("sets session span status to ok on success")
  it("sets session span status to error on exception")
  it("does not suppress exceptions")
  it("flushes span even when agent throws")
  it("sets conversationId on span")
  it("does NOT create LLM call spans without provider patch")
})

describe("recordLlmCall", () => {
  it("creates a gen_ai.llm.call span with token counts")
  it("sets provider and model attributes")
})
```

---

---