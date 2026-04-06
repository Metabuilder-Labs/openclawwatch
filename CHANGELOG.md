# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
- TypeScript SDK (`@ocw/sdk`): `OcwClient` and `SpanBuilder` for Node.js agents
- Auto-bootstrap: TracerProvider initializes lazily on first `@watch()` or `patch_*()` call
- Community-maintained model pricing table (`pricing/models.toml`)
- Session continuity via `conversation_id` across process restarts
- GitHub Actions CI (Python 3.10/3.11/3.12 + TypeScript)
