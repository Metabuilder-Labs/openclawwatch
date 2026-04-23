# Roadmap

## Completed

- [x] `ocw serve` background daemon (launchd / systemd)
- [x] Web UI for `ocw serve`
- [x] LiteLLM provider patch
- [x] `ocw stop` and `ocw uninstall` commands
- [x] Claude Code integration (`ocw onboard --claude-code`)
- [x] `ocw budget` CLI, API route, and web UI
- [x] `ocw drift` CLI with Z-score reporting
- [x] Full pipeline wiring (alerts, schema validation, drift detection in `ocw serve`)
- [x] MCP server (`ocw mcp`) — 13 tools for Claude Code, no `ocw serve` dependency

## Planned

- [ ] `ocw watch` — live tail mode for spans
- [ ] `ocw replay` — replay captured sessions against new model versions
- [ ] Vercel AI SDK integration (TypeScript)
- [ ] Azure AI Agent Service integration
- [ ] TypeScript framework patches (LangChain JS, OpenAI Agents SDK)
- [ ] Mastra integration (TypeScript)
- [ ] Docker image
- [ ] GitHub Actions integration for CI drift/cost checks
