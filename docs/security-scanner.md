# Security Scanner

The security scanner runs 10 sentinel modules written in Rust. Each module focuses on a specific attack surface. The scanner is designed to catch things that vibe coders accidentally introduce — leaked secrets, unsafe shell calls, suspicious dependencies, and container misconfigurations.

## Sentinel Modules

### 1. Secrets

Detects hardcoded credentials, API keys, tokens, and passwords in source code and config files.

Patterns detected:
- AWS access keys and secret keys (`AKIA...`)
- GitHub/GitLab personal access tokens
- Anthropic, OpenAI, Cohere API keys
- JWT tokens, Bearer tokens in code
- Database connection strings with passwords
- Private keys (RSA, EC, Ed25519)
- `.env` files committed to git
- Base64-encoded secrets in config files

Ignores: test fixtures, example configs with placeholder values, `.env.example` files.

### 2. Network

Scans for unsafe network patterns.

Checks for:
- Hardcoded IP addresses (non-localhost)
- HTTP URLs where HTTPS should be used
- `0.0.0.0` bindings in production config
- Disabled SSL verification (`verify=False`, `rejectUnauthorized: false`)
- Open CORS (`*` origin)
- WebSocket connections without authentication
- Fetching remote scripts via HTTP

### 3. Filesystem

Detects dangerous file operations.

Checks for:
- Path traversal patterns (`../` in user-controlled paths)
- World-writable file permissions
- Temporary file usage without secure cleanup
- Symlink following without validation
- Writes to system directories
- Reading files with user-controlled paths without sanitization

### 4. Process

Identifies unsafe process execution.

Checks for:
- Shell injection via `os.system()`, `subprocess.Popen(shell=True)`
- `eval()` / `exec()` with external input
- `child_process.exec()` in Node.js
- Unsanitized command-line argument usage
- `pickle.loads()` on untrusted data
- `yaml.load()` without `SafeLoader`

### 5. Supply Chain

Analyzes dependencies for known risks.

Checks for:
- Dependencies with known CVEs (checks against local advisory DB)
- Packages with install scripts (`preinstall`, `postinstall`)
- Typosquatting candidates (edit distance from popular packages)
- Pinned vs. floating version ranges
- Dependencies pulled from non-standard registries
- Excessive dependency count (flags projects with 200+ direct deps)

### 6. Git Hooks

Inspects git hooks for malicious behavior.

Checks for:
- Pre-commit/post-checkout hooks that download and execute remote code
- Hooks that modify source files silently
- Hooks that exfiltrate environment variables
- Hooks installed by dependencies (not by the developer)
- Hidden hooks in `.git/hooks` that don't match committed `.husky` or `.githooks` configs

### 7. Container Escape

Docker and container security checks.

Checks for:
- `--privileged` flag in docker-compose or run commands
- Mounted Docker socket (`/var/run/docker.sock`)
- `SYS_ADMIN` and other dangerous capabilities
- Running as root without `USER` directive
- Host network mode
- Writable volume mounts to sensitive host paths
- Missing health checks in Dockerfiles

### 8. Autostart

Detects persistence mechanisms that survive reboots.

Checks for:
- LaunchAgents/LaunchDaemons (macOS)
- systemd service files
- Windows Registry run keys
- cron `@reboot` entries
- Login items and startup scripts
- npm/pip global install scripts that modify shell profiles

### 9. Crontab

Analyzes scheduled tasks for risks.

Checks for:
- Cron jobs downloading and executing remote scripts
- Jobs running with elevated privileges
- Jobs without logging or error handling
- Scheduled tasks referencing deleted or moved scripts
- High-frequency jobs (every minute) without rate limiting

### 10. Env Leak

Detects environment variable exposure.

Checks for:
- `process.env` or `os.environ` dumped to logs
- Environment variables passed to error reporting services
- Debug pages that display environment (Django debug, etc.)
- `.env` files in Docker build context (not in `.dockerignore`)
- Server-side env vars exposed to client-side bundles
- `printenv` or `env` commands in scripts without filtering

## Cross-Platform Coverage

Each module adapts its checks to the current OS:

| Module | Linux | macOS | Windows |
|--------|-------|-------|---------|
| Secrets | Full | Full | Full |
| Network | Full | Full | Full |
| Filesystem | Full | Full | Adapted paths |
| Process | Full | Full | PowerShell patterns added |
| Supply Chain | Full | Full | Full |
| Git Hooks | Full | Full | Full |
| Container Escape | Full | Full (Docker Desktop) | Full (Docker Desktop) |
| Autostart | systemd | LaunchAgent | Registry |
| Crontab | cron/systemd timers | cron/launchd | Task Scheduler |
| Env Leak | Full | Full | Full |

## Output

Each finding includes:
```json
{
  "module": "secrets",
  "severity": "high",
  "file": "config/settings.py",
  "line": 42,
  "pattern": "ANTHROPIC_API_KEY = \"sk-ant-...\"",
  "message": "Hardcoded Anthropic API key detected",
  "recommendation": "Move to environment variable, add to .gitignore if in .env file",
  "cwe": "CWE-798"
}
```

CWE references are provided where applicable to map findings to industry-standard weakness classifications.

## Performance

The Rust sentinel modules scan a typical 50K-line codebase in under 2 seconds. File I/O is parallelized using rayon, and regex patterns are compiled once and reused across files.

## False Positive Handling

The scanner respects inline suppression comments:
```python
api_key = get_key()  # fartrun:ignore secrets
```

Project-wide suppression in `config.toml`:
```toml
[alert_filters]
ignore_patterns = ["test_fixtures/fake_keys.py"]
ignore_modules = ["secrets"]  # disable entire module
```
