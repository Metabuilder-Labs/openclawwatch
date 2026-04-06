# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
