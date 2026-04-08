# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.4] - 2026-04-08

### Fixed
- SDK DuckDB lock error when `ocw serve` is running — bootstrap now detects the server and sends spans via HTTP (`OcwHttpExporter`) instead of opening DuckDB directly
- LiteLLM model names no longer include provider prefix (`gpt-4o-mini` not `openai/gpt-4o-mini`), fixing pricing lookup failures
- LiteLLM streaming wrappers now correctly attribute provider and stripped model name

### Added
- OpenClaw integration — zero-code OTLP ingestion for OpenClaw agents (PR #15)
- Web UI restyled to opencla.watch palette (deep navy + electric blue, IBM Plex Mono, Bricolage Grotesque)
- Inline SVG logo in web UI sidebar

### Changed
- Node.js upgraded from 20 to 22 in CI and publish workflows
- npm SDK bumped to 0.1.4 (matching Python release)
- README: added Web UI section, updated roadmap (4 items complete, 5 new)

## [0.1.3] - 2026-04-07

### Added
- **Web UI** — local dashboard served by `ocw serve` at `http://127.0.0.1:7391/`
  - Status view with agent cards, cost, tokens, alerts (auto-refresh 5s)
  - Traces view with span waterfall visualization and click-to-inspect detail
  - Cost view with breakdown by day/agent/model/tool and summary totals
  - Alerts view with severity filtering and expandable JSON detail
  - Drift view with baseline vs latest session Z-score pass/fail
- `GET /api/v1/status` endpoint — agent status data (mirrors `ocw status --json`)
- Drift endpoint now lists all agents when `agent_id` is omitted
- LiteLLM provider integration (`patch_litellm()`)
- Single-file Preact SPA — no build step, dark theme, JetBrains Mono

### Changed
- CORS updated to regex matching for `localhost:*` ports
- API key injected into UI via `<meta>` tag (no user prompt needed)

## [0.1.2] - 2026-04-07

### Fixed
- `ocw serve` printing wrong metrics port (9464 instead of 7391)
- `ocw onboard` launchd daemon install now degrades gracefully on failure instead of crashing
- CLI commands now fall back to REST API when DuckDB is locked by `ocw serve`

### Added
- `ocw stop` command — graceful shutdown of daemon or background process
- `ocw uninstall` command — clean removal of all OCW data, config, and daemon
- 16 runnable example agents across 4 tiers: single provider, single framework, multi-agent, and alerts/drift demos
- API fallback backend (`ApiBackend`) so CLI works while `ocw serve` holds the DB lock

### Changed
- README: added toy agent quick-start, example agents section, corrected metrics URL, updated CLI reference
- CLAUDE.md: updated CLI command table, repo layout, added PyPI package name rule

## [0.1.1] - 2026-04-06

### Fixed
- `ocw export` returning empty output due to corrupted DuckDB span indexes
- `ocw status` showing `?` instead of `●` for completed sessions
- `ocw status` showing `$0.000000` cost due to `date.today()` vs UTC date mismatch
- `ocw cost` showing spurious `$0.000000` row from session-level spans with no model

### Added
- `ocw trace` prefix matching — short trace IDs now resolve like git short hashes
- PyPI and npm publish workflows (`publish-pypi.yml`, `publish-npm.yml`)
- PyPI metadata: README as long description, classifiers, project URLs
- `CODEOWNERS` requiring review from @anilmurty

### Changed
- Renamed npm package from `@ocw/sdk` to `@openclawwatch/sdk`
- Consolidated `AGENTS.md` to point at `CLAUDE.md` as source of truth

## [0.1.0] - 2026-04-05

### Added
- Core observability pipeline: span ingestion, session tracking, cost calculation
- DuckDB storage backend with migration runner
- 13 alert types with 6 dispatch channels (stdout, file, ntfy, webhook, Discord, Telegram)
- Z-score behavioral drift detection with automatic baseline building
- JSON Schema validation for tool outputs (declared or genson-inferred)
- CLI commands: `onboard`, `status`, `traces`, `cost`, `alerts`, `drift`, `tools`, `export`, `serve`, `doctor`
- REST API with OTLP JSON ingest endpoint and Prometheus metrics
- Python SDK: `@watch()` decorator, `patch_anthropic()`, `patch_openai()`, and 9 more provider/framework integrations
- TypeScript SDK (`@openclawwatch/sdk`): `OcwClient` and `SpanBuilder` for Node.js agents
- Auto-bootstrap: TracerProvider initializes lazily on first `@watch()` or `patch_*()` call
- Community-maintained model pricing table (`pricing/models.toml`)
- Session continuity via `conversation_id` across process restarts
- GitHub Actions CI (Python 3.10/3.11/3.12 + TypeScript)
