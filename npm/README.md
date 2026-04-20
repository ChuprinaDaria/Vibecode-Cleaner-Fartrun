# fartrun

**Your AI wrote the code. We check if it'll get you fired.**

MCP server installer for Claude Code, Cursor & Windsurf. Rust-powered local code scanner. 29 tools. Zero tokens. Zero cloud.

## Install

```bash
npx fartrun@latest install
```

Downloads the MCP binary for your OS and configures your editor automatically.

```bash
npx fartrun@latest install --claude    # Claude Code only
npx fartrun@latest install --cursor    # Cursor only
npx fartrun@latest install --windsurf  # Windsurf only
npx fartrun@latest mcp-config          # Print MCP config JSON
```

## What you get (29 MCP tools)

- **Security Scanner** — 10 Rust modules (processes, network, filesystem, secrets, supply chain)
- **Health Scanner** — 9-phase project audit (~95% accuracy across Python/Go/TS/React/Django)
- **Token Monitor** — Claude Code spending tracker
- **Save Points** — rollback to any previous state
- **Frozen Files** — lock files from AI edits

Desktop GUI available separately via [Releases](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun/releases).

## Platforms

| OS | Architecture |
|----|-------------|
| Linux | x64 |
| macOS | x64, arm64 (Rosetta) |
| Windows | x64 |

## Links

- [GitHub](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun)
- [Releases](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun/releases)

## License

Fart & Run License v1.0 — Copyright (c) 2026 Daria Chuprina
