# 13 — Lifecycle Commands & Bug Fixes

## Bug Fixes

### 1. Metrics endpoint prints wrong port
`ocw serve` prints `http://127.0.0.1:9464/metrics` but metrics are served on the main API port via FastAPI route, not a separate Prometheus server.

**Fix:** Print `http://{bind_host}:{bind_port}/metrics` in `cmd_serve.py`.

### 2. Launchd daemon fails to load
`launchctl load` fails with "Input/output error". Degrade gracefully — catch the error and suggest `ocw serve &` as fallback.

### 3. DuckDB lock when `ocw serve` is running
DuckDB allows only one connection. CLI commands should detect a running server and query via REST API instead of opening DuckDB directly.

**Fix:** In `cli/main.py`, before opening DuckDB, probe `http://{host}:{port}/api/v1/traces?limit=1`. If the server responds, inject an `ApiBackend` that routes `StorageBackend` calls through HTTP instead of DuckDB.

## New Commands

### `ocw stop`
- Unload launchd daemon if present, else SIGTERM the `ocw serve` process
- Print confirmation or "not running" message

### `ocw uninstall`
- Stop server, delete plist, delete `~/.ocw/`, delete temp files
- Require `--yes` or interactive confirmation before deleting

## README Updates
- Add toy_agent example
- Review and improve overall documentation
