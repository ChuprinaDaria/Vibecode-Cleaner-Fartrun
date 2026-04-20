# Plugins

Fartrun supports a plugin system for extending health checks, adding custom scanners, and integrating with external tools. Plugins follow a simple Python ABC contract.

## Built-in Plugins

### `security_scan`

Runs the 10-module Rust security sentinel. Integrated into the main scan pipeline at phase level. Findings appear alongside health scan results with CWE references.

### `test_runner`

Discovers and executes test suites. Auto-detects the test framework (pytest, jest, go test, cargo test). Reports pass/fail counts, coverage percentage, and slow tests. Findings feed into the Test Coverage scan phase.

### `docker_monitor`

Analyzes Docker configuration in the project.

Checks:
- Dockerfile best practices (multi-stage builds, non-root user, layer caching)
- docker-compose.yml validation (service dependencies, volume mounts, network config)
- Image size estimation and optimization suggestions
- Security: privileged mode, host mounts, exposed ports

### `port_map`

Scans the project for network port usage and potential conflicts.

Detects:
- Hardcoded port numbers in source code and config files
- Port conflicts between services in docker-compose
- Common port collisions (3000, 5432, 6379, 8000, 8080)
- Ports defined in environment variables vs. code

## Plugin ABC Contract

Every plugin must implement the `FartrunPlugin` abstract base class:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Alert:
    severity: str        # "high", "medium", "low", "info"
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    rule_id: Optional[str] = None


@dataclass
class PluginResult:
    title: str
    summary: str
    alerts: list[Alert]
    data: dict           # arbitrary structured data for rendering


class FartrunPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier. Lowercase, no spaces."""
        ...

    @property
    @abstractmethod
    def icon(self) -> str:
        """Single emoji for display in GUI and CLI output."""
        ...

    @abstractmethod
    def migrate(self) -> None:
        """
        Called once on plugin registration. Use for setup:
        creating database tables, downloading models, checking dependencies.
        Must be idempotent — safe to call multiple times.
        """
        ...

    @abstractmethod
    def collect(self, project_dir: str) -> PluginResult:
        """
        Run the plugin's analysis on the given project directory.
        Returns a PluginResult with alerts and arbitrary data.
        This is called during `fartrun scan` and by MCP health tools.
        """
        ...

    @abstractmethod
    def render(self, result: PluginResult) -> str:
        """
        Render the result as a human-readable string for CLI output.
        The GUI uses result.data directly for structured display.
        """
        ...

    @abstractmethod
    def get_alerts(self, result: PluginResult) -> list[Alert]:
        """
        Extract alerts from the result. Usually just returns result.alerts,
        but can filter or transform based on config.
        """
        ...
```

## Writing a Custom Plugin

### Step 1: Create the Plugin File

Place your plugin in the custom plugins directory (default: `~/.config/fartrun/plugins/`).

```python
# ~/.config/fartrun/plugins/license_checker.py

from fartrun.plugins import FartrunPlugin, PluginResult, Alert
import os


class LicenseChecker(FartrunPlugin):
    @property
    def name(self) -> str:
        return "license_checker"

    @property
    def icon(self) -> str:
        return "\u2696\ufe0f"

    def migrate(self) -> None:
        pass

    def collect(self, project_dir: str) -> PluginResult:
        alerts = []
        license_file = None

        for candidate in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]:
            path = os.path.join(project_dir, candidate)
            if os.path.exists(path):
                license_file = candidate
                break

        if license_file is None:
            alerts.append(Alert(
                severity="medium",
                message="No LICENSE file found in project root",
                rule_id="license-missing"
            ))

        # Check for license headers in source files
        source_count = 0
        header_count = 0
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__"}]
            for f in files:
                if f.endswith((".py", ".ts", ".js", ".go", ".rs")):
                    source_count += 1
                    filepath = os.path.join(root, f)
                    with open(filepath, "r", errors="ignore") as fh:
                        head = fh.read(500)
                        if "license" in head.lower() or "copyright" in head.lower():
                            header_count += 1

        ratio = header_count / source_count if source_count > 0 else 0

        return PluginResult(
            title="License Check",
            summary=f"License file: {license_file or 'MISSING'}. "
                    f"Header coverage: {header_count}/{source_count} ({ratio:.0%})",
            alerts=alerts,
            data={
                "license_file": license_file,
                "source_files": source_count,
                "files_with_headers": header_count,
                "coverage_ratio": ratio,
            }
        )

    def render(self, result: PluginResult) -> str:
        lines = [f"  {self.icon} {result.title}", f"     {result.summary}"]
        for alert in result.alerts:
            lines.append(f"     [{alert.severity.upper()}] {alert.message}")
        return "\n".join(lines)

    def get_alerts(self, result: PluginResult) -> list[Alert]:
        return result.alerts
```

### Step 2: Register the Plugin

Add the plugin to `config.toml`:

```toml
[plugins]
enabled = ["security_scan", "test_runner", "docker_monitor", "port_map", "license_checker"]
custom_dir = "~/.config/fartrun/plugins"
```

Fartrun discovers plugins by scanning the `custom_dir` for Python files that contain a class inheriting from `FartrunPlugin`.

### Step 3: Test

```bash
fartrun scan -v    # plugin output appears after built-in phases
```

## Plugin Lifecycle

1. **Discovery**: On startup, fartrun scans built-in and custom plugin directories
2. **Registration**: Plugin classes are instantiated, `name` and `icon` are read
3. **Migration**: `migrate()` is called once (tracked in SQLite to avoid re-running)
4. **Collection**: During scan, `collect()` is called with the project directory
5. **Rendering**: CLI calls `render()`, GUI reads `result.data` directly
6. **Alerting**: `get_alerts()` feeds into the unified alert system

## Plugin Guidelines

- Keep `collect()` fast — under 5 seconds for a typical project
- Never modify project files from a plugin
- Use `rule_id` on alerts so users can suppress specific findings in `alert_filters`
- Handle missing dependencies gracefully in `migrate()`
- Respect `.gitignore` patterns when walking the file tree
- Log verbose output to `logging.getLogger("fartrun.plugins.your_name")`
