# Task: Build local Web UI for `ocw serve`

## Overview

Add a local web UI served by `ocw serve` that gives developers a visual interface to their telemetry data. The UI is a visual upgrade from the CLI — data tables, trace detail, span waterfall. It consumes the existing REST API endpoints with no new backend work.

---

## Architecture

### Serving approach
- Serve as static files from `ocw serve` — add a catch-all route that serves an SPA
- Single HTML file with embedded JS/CSS — no build step, no node_modules, no webpack
- Use vanilla JS + a lightweight reactive library (Alpine.js or Preact via CDN)
- The UI fetches data from the existing API endpoints on the same host/port
- Add CORS for `http://localhost:*` and `http://127.0.0.1:*`

### File location
```
ocw/
└── ui/
    └── index.html
```

### Route setup
- `GET /` → serves `index.html` (replace the current 404)
- `GET /ui/*` → serves `index.html` (SPA catch-all for client-side routing)
- All existing `/api/v1/*` and `/metrics` routes unchanged
- `/docs` still serves Swagger

---

## Implementation sequence

Build this in three sequential phases. Complete and verify each phase before moving to the next.

### Phase 1: Scaffold + Status page

**Goal:** Get the SPA shell working with nav, routing, API auth, and the first useful view.

1. Create `ocw/ui/index.html` with the full HTML/CSS/JS scaffold
2. Implement hash-based routing (`/#/status`, `/#/traces`, `/#/cost`, `/#/alerts`, `/#/drift`)
3. Build the sidebar nav with all 5 view links
4. Implement API auth — read ingest secret from a meta tag injected by the server, or prompt on first load and store in sessionStorage
5. Add the FastAPI route changes: serve `index.html` at `/` and `/ui/*`
6. Build the **Status page** (see spec below)

**Verify before moving on:**
- `ocw serve` opens to the web UI at `http://127.0.0.1:7391/`
- Nav links switch between views (other views can show "coming soon" placeholders)
- Status page loads and displays agent data from the API
- `/docs` and `/api/v1/*` still work

### Phase 2: Traces + Span waterfall

**Goal:** Build the most important visualization — the span waterfall.

1. Build the **Traces list view** (see spec below)
2. Build the **Trace detail view** with span waterfall (see spec below)
3. The waterfall is the single most important piece of UI. Get this right before moving on.

**Verify before moving on:**
- Trace list loads and filters work
- Clicking a trace opens the detail view with a correct span waterfall
- Multi-span traces render with proper nesting (test with `examples/single_provider/anthropic_agent.py`)
- Single-span traces still render (just one bar at full width)
- Clicking a span in the waterfall populates the detail panel

### Phase 3: Cost + Alerts + Drift

**Goal:** Complete the remaining three views. These follow a simpler pattern — mostly data tables with filters.

1. Build the **Cost view** (see spec below)
2. Build the **Alerts view** (see spec below)
3. Build the **Drift view** (see spec below)

**Verify:**
- Cost view totals match `ocw cost` CLI output
- Alerts view shows alerts from `examples/alerts_and_drift/sensitive_actions_demo.py`
- Drift view shows baseline and violations from `examples/alerts_and_drift/drift_demo.py`

---

## View specifications

### 1. Status (home page, default view)

Current state of all agents — the visual equivalent of `ocw status`.

**Layout:**
- One card per agent: agent ID, status (active/idle), current session ID, cost today vs daily budget (progress bar), token counts (in/out), tool call count, time since last span
- Below agent cards: "Recent alerts" list — last 5 alerts with severity badges

**API calls:** `/api/v1/cost?group_by=agent`, `/api/v1/alerts?since=24h`

**Auto-refresh:** Poll every 5 seconds.

### 2. Traces

Trace list with drill-down to span waterfall — the visual equivalent of `ocw traces` + `ocw trace <id>`.

**List view:**
- Table: trace ID (truncated), agent ID, root span name, start time (relative), duration, cost, status (color dot), span count
- Filter bar: agent ID dropdown, status filter, time range (1h / 6h / 24h / 7d)
- Click a row to open detail view

**Detail view:**
- **Span waterfall** (see dedicated section below)
- Detail panel below showing selected span's full attributes: model, provider, tokens, cost, status, tool name, all raw attributes
- Back button to return to list

**API calls:** `/api/v1/traces` for list, `/api/v1/traces/{trace_id}` for detail

### 3. Cost

Cost breakdown — the visual equivalent of `ocw cost`.

**Layout:**
- Summary row: total cost, total input tokens, total output tokens for selected period
- Table grouped by selected dimension: group label, input tokens, output tokens, cost USD
- Group-by selector: agent / model / day / tool
- Time range filter: 1h / 6h / 24h / 7d / 30d

**API calls:** `/api/v1/cost?group_by={dimension}&since={range}`

### 4. Alerts

Alert history — the visual equivalent of `ocw alerts`.

**Layout:**
- Table: fired_at (relative time), type (badge), severity (color: critical=red, warning=yellow, info=blue), title, agent ID
- Click row to expand inline: full detail JSON + link to related trace
- Filter bar: severity dropdown, type dropdown, agent ID dropdown

**API calls:** `/api/v1/alerts`

### 5. Drift

Drift report — the visual equivalent of `ocw drift`.

**Layout:**
- One section per agent with drift enabled
- Baseline info: sample count, when computed
- Per-dimension row: metric name, baseline mean ± stddev, latest session value, Z-score, pass/fail (green/red)
- If no baseline: "N of M sessions collected" progress indicator

**API calls:** `/api/v1/drift`

---

## Span waterfall — detailed spec

This is the single most important visualization. It's the main reason developers will use the web UI over the CLI.

### Rendering
- Each span is a horizontal bar positioned on a timeline
- X-axis: time from trace start (0ms) to trace end
- Y-axis: spans stacked vertically, indented by parent-child nesting depth
- Bar width = span duration proportional to total trace duration
- Bar color by span kind:
  - `invoke_agent` / agent spans: `#00E5A0` (accent green)
  - `invoke_llm` / LLM calls: `#3D8EFF` (blue)
  - `invoke_tool` / tool calls: `#D29922` (orange)
  - Other: `#8B949E` (gray)
- Bar label: span name + duration (e.g. "invoke_llm (claude-haiku-4-5) — 340ms")
- Hover: highlight bar, show tooltip with key attributes
- Click: select span, populate detail panel below

### Building the tree
Use `parent_span_id` from span data to build the hierarchy:
```
trace
├── invoke_agent (my-agent) — 1200ms
│   ├── invoke_llm (claude-haiku-4-5) — 340ms
│   ├── invoke_tool (calculator) — 12ms
│   └── invoke_llm (claude-haiku-4-5) — 280ms
```

### Empty state
Single-span traces: render one bar at full width.
No traces at all: show a helpful message pointing to the quickstart.

---

## Navigation

### Sidebar
```
[OpenClawWatch]

● Status
⟡ Traces
$ Cost
⚠ Alerts
⌇ Drift

─────────
API docs →     (/docs)
GitHub →       (repo link)
v0.1.0
```

- Active view: accent color highlight
- Width: ~200px, compact
- Collapsible on narrow viewports

---

## Visual design

### Colors
- Background: `#0D1117`
- Surface/cards: `#161B22`
- Borders: `#30363D`
- Text primary: `#E6EDF3`
- Text secondary: `#8B949E`
- Accent/success: `#00E5A0`
- Warning: `#D29922`
- Error/critical: `#F85149`
- Info/blue: `#3D8EFF`

### Typography
- UI chrome (nav, labels, headers, badges): `JetBrains Mono`, monospace
- Data values (costs, tokens, durations): `JetBrains Mono`, monospace
- Body text (descriptions, empty states): system sans-serif (`-apple-system, BlinkMacSystemFont, 'Segoe UI', ...`)

### Principles
- Dark theme only — matches the brand
- Dense information display — this is a dev tool, favor data density over whitespace
- No loading states for responses under 200ms (local DuckDB is fast)
- Desktop-first — this runs on localhost

---

## Implementation notes

- **Single file SPA:** Everything in `index.html`. `<style>` and `<script>` blocks. Import Alpine.js or Preact from CDN. No build step.
- **API auth:** Existing API requires key via `Authorization` or `X-API-Key` header. Inject the key via a meta tag from the server, or prompt on first load and store in sessionStorage.
- **Auto-refresh:** Status page polls every 5s. Other pages have a manual refresh button.
- **URL routing:** Hash-based (`/#/traces`, `/#/cost`, etc.) — no server routing changes needed beyond the catch-all.
- **No new Python dependencies.** The UI is pure static files served by FastAPI's `StaticFiles` or inline route handlers.

---

## Verification

- `ocw serve` opens to the web UI at `http://127.0.0.1:7391/`
- All 5 views render with real span data
- Span waterfall renders correctly for multi-span traces
- Cost totals match `ocw cost` CLI output
- Alerts visible from alert demo examples
- Drift view shows baseline and violations from drift demo
- `/docs` Swagger still works
- No new Python dependencies
- All existing tests pass
- `ruff check ocw/` passes