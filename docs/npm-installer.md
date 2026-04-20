# npm Installer

The npm package provides a zero-dependency installer that downloads the correct fartrun binary for your platform and configures MCP integration with your AI coding tools.

## Quick Start

```bash
npx fartrun@latest install
```

That single command:
1. Detects your OS and architecture
2. Downloads the correct binary from GitHub Releases
3. Places it in a standard location
4. Configures MCP in detected AI coding tools
5. Verifies the installation

## How It Works

### Platform Detection

The installer reads `process.platform` and `process.arch` to determine which binary to download:

| `process.platform` | `process.arch` | Binary |
|---------------------|----------------|--------|
| `linux` | `x64` | `fartrun-linux-x86_64` |
| `linux` | `arm64` | `fartrun-linux-aarch64` |
| `darwin` | `x64` | `fartrun-macos-x86_64` |
| `darwin` | `arm64` | `fartrun-macos-aarch64` |
| `win32` | `x64` | `fartrun-windows-x86_64.exe` |

Unsupported combinations (e.g., Windows ARM) exit with a clear error message.

### Binary Download

The installer fetches the binary from the latest GitHub Release:
```
https://github.com/user/fartrun/releases/latest/download/{binary_name}
```

Download includes:
- SHA256 checksum verification against the published `.sha256` file
- Progress bar for large downloads
- Retry logic (3 attempts with exponential backoff)

### Installation Path

| OS | Default Path |
|----|-------------|
| Linux | `~/.local/bin/fartrun` |
| macOS | `~/.local/bin/fartrun` |
| Windows | `%LOCALAPPDATA%\fartrun\fartrun.exe` |

The installer sets executable permissions on Linux/macOS (`chmod +x`). On Windows, the directory is added to the user's PATH if not already present.

### MCP Configuration

After installing the binary, the installer scans for AI coding tools and configures MCP integration.

#### Claude Code

Writes to `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "fartrun": {
      "command": "/home/user/.local/bin/fartrun",
      "args": ["mcp"]
    }
  }
}
```

If `settings.json` already exists, the installer merges the `fartrun` entry into the existing `mcpServers` object without touching other servers.

#### Cursor

Writes to `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "fartrun": {
      "command": "/home/user/.local/bin/fartrun",
      "args": ["mcp"]
    }
  }
}
```

#### Windsurf

Writes to `~/.windsurf/mcp.json`:
```json
{
  "mcpServers": {
    "fartrun": {
      "command": "/home/user/.local/bin/fartrun",
      "args": ["mcp"]
    }
  }
}
```

The installer only configures tools it detects on the system (by checking for the config directory existence). It never creates config directories for tools you don't have.

## Other Commands

### `npx fartrun@latest uninstall`

Removes the binary and MCP configuration from all detected tools.

### `npx fartrun@latest update`

Downloads the latest binary, replacing the current one. MCP config is preserved.

### `npx fartrun@latest status`

Shows:
- Installed binary path and version
- Configured MCP clients
- Binary health check (runs `fartrun --version`)

## Flags

| Flag | Description |
|------|-------------|
| `--claude-only` | Only configure Claude Code |
| `--cursor-only` | Only configure Cursor |
| `--windsurf-only` | Only configure Windsurf |
| `--no-mcp` | Skip MCP configuration, only install binary |
| `--bin-dir <path>` | Override binary installation directory |
| `--verbose` | Show detailed output |

## Manual Installation

If you prefer not to use npm:

1. Download the binary from [GitHub Releases](https://github.com/user/fartrun/releases/latest)
2. Place it somewhere in your PATH
3. Make it executable: `chmod +x fartrun`
4. Configure MCP manually in your tool's settings (see config examples above)

## Troubleshooting

### "Permission denied" on Linux/macOS

The installer needs write access to `~/.local/bin/`. Create it if it doesn't exist:
```bash
mkdir -p ~/.local/bin
```

### Binary not found after install

Ensure `~/.local/bin` is in your PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### MCP not working after install

1. Restart your AI coding tool (Claude Code, Cursor, Windsurf)
2. Verify the binary path in the MCP config is correct
3. Test the binary directly: `fartrun --version`
4. Check MCP server: `echo '{"jsonrpc":"2.0","method":"initialize","id":1}' | fartrun mcp`

### Proxy/Firewall Issues

The installer respects `HTTP_PROXY` and `HTTPS_PROXY` environment variables:
```bash
HTTPS_PROXY=http://proxy:8080 npx fartrun@latest install
```
