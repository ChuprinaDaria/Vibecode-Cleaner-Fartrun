# Awesome MCP Listing — Vibecode Cleaner Fartrun

## Entry for awesome-mcp README

| Name | Description | Install |
|------|-------------|---------|
| [Vibecode Cleaner Fartrun](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun) | Rust-powered local code scanner. 29 MCP tools: security vulns, dead code, health checks, save points, frozen files. Zero tokens consumed — all analysis runs as compiled code, not AI. | `pip install fartrun` |

## Category

Developer Tools

## Full Description (for PR body)

**Vibecode Cleaner Fartrun & Awesome Hasselhoff**

Not another AI reviewing AI. A Rust-powered code scanner that actually reads your codebase locally — zero extra tokens consumed, no code leaves your machine.

**29 MCP tools** across 6 categories:
- **Health scanning** — 9-phase project audit (dead code, tech debt, git hygiene, framework checks) with Context7 doc enrichment
- **Security** — 10 Rust sentinel modules (processes, network, secrets, supply chain, env leaks)
- **Save points** — git-based checkpoints with one-click rollback
- **Frozen files** — lock files from AI modification via CLAUDE.md
- **Code search** — grep-style keyword search across project
- **Prompt building** — structured prompts from vibe descriptions

**Key differentiator:** All analysis is compiled Rust code running locally. No API calls for scanning. No token budget impact. Results in milliseconds, not seconds.

**Transports:** stdio (Claude Code, settings.json) + HTTP/SSE (Cursor, Windsurf, web clients)

**Tested accuracy:** ~95% across 12 real projects (Python, Go, TypeScript, Django, FastAPI, React).

Also farts at you and has Hasselhoff. But you probably care about the Rust part more.

## MCP Config (stdio)

```json
{
  "mcpServers": {
    "fartrun": {
      "command": "fartrun-mcp"
    }
  }
}
```

## MCP Config (HTTP)

```json
{
  "mcpServers": {
    "fartrun": {
      "url": "http://localhost:3001/sse"
    }
  }
}
```

Start server: `fartrun mcp --http --port 3001`

## Roadmap: v2.0 (npx)

```json
{
  "mcpServers": {
    "fartrun": {
      "command": "npx",
      "args": ["fartrun@latest"]
    }
  }
}
```

v2.0 will publish an npm package so `npx fartrun@latest` auto-downloads the latest version each time. No manual updates needed.
