# Desktop GUI

Fartrun includes a Win95-themed PyQt5 desktop application for developers who prefer a visual interface. The retro aesthetic is intentional — it makes the tool feel approachable and keeps the focus on information rather than flashy design.

## Starting the GUI

```bash
fartrun gui                    # launch the desktop app
fartrun gui --no-tray          # launch without system tray icon
```

The GUI is optional and not required for any functionality. Everything it does is also available via CLI and MCP.

## Pages

### Overview

The landing page. Shows:
- Project health score (0-100) as a large gauge
- Stack detection results (languages, frameworks, package managers)
- Last scan timestamp
- Quick action buttons: Scan, Save, Rollback
- Top 5 issues from the most recent scan
- Save point count and frozen file count

### Dev Health

Full scan results browser. Organized by the 9 scanner phases.

Features:
- Collapsible phase sections with issue counts
- Severity filters (show only high, medium, etc.)
- Click any finding to open the file at the correct line in your editor
- Export report as Markdown or JSON
- Re-scan button with progress bar
- Diff view: compare current scan with previous scan to track improvements

### Safety Net

Manage save points and rollbacks.

Features:
- Timeline view of all save points with labels, timestamps, and scores
- One-click rollback with confirmation dialog
- Create save point with custom label
- View diff between any two save points
- Backup branch cleanup tool
- Visual indicator when there are uncommitted changes

### Activity

Chronological log of all fartrun operations.

Shows:
- Scans with score changes
- Save points created
- Rollbacks performed
- Files frozen/unfrozen
- Hook blocks (attempted edits to frozen files)
- Context7 installs/uninstalls

Each entry has a timestamp, operation type, and details. Filterable by operation type and date range.

### Security

Security sentinel results in a dedicated view.

Features:
- Findings grouped by sentinel module (Secrets, Network, etc.)
- Severity-based color coding
- Inline suppression: right-click a finding to add `fartrun:ignore` comment
- CWE reference links for each finding type
- Export for security audit reports

### Frozen Files

Visual manager for file protection.

Features:
- List of all frozen files with freeze timestamp
- Drag-and-drop files from file browser to freeze them
- Unfreeze button with confirmation
- Glob pattern support for bulk freeze
- Visual file tree with frozen files highlighted
- Hook status indicator (installed/not installed)

### Prompt Helper

Build AI-ready prompts with scan context.

Features:
- Select which scan phases to include in the prompt
- Choose focus area (security, performance, refactoring, etc.)
- Preview the generated prompt
- Copy to clipboard
- Token count estimate
- History of generated prompts

### Settings

Configuration editor.

Features:
- Visual editor for `config.toml` (no need to edit files manually)
- Sound enable/disable toggles with preview playback
- Hasselhoff mode toggle
- Alert threshold sliders
- Plugin enable/disable
- Data directory path configuration
- Theme selection (Win95 is default, also available: Win98, WinXP — all equally retro)

## System Tray

When running, fartrun places an icon in the system tray (notification area).

Tray features:
- Left-click: open/focus the main window
- Right-click menu:
  - Quick Scan
  - Create Save Point
  - Last Score display
  - Open Settings
  - Quit

Tray notifications:
- Scan complete (with score)
- High-severity finding detected
- Save point created
- Frozen file edit blocked by hook

Notifications use the OS-native notification system (libnotify on Linux, NSUserNotification on macOS, toast on Windows).

## Hasselhoff Wizard

An easter egg that activates when scan scores drop below 40 or when the user explicitly summons it from Settings.

The wizard displays a retro animated David Hasselhoff encouraging you to fix your code, accompanied by one of three songs:
- "Looking for Freedom" — plays when code needs liberation from tech debt
- "True Survivor" — plays during rollback operations
- "Du" — plays for German locale users or when explicitly selected

The wizard uses platform-appropriate audio playback and can be permanently disabled in Settings. It respects the `sounds.enabled` config flag.

## Architecture

The GUI is built with:
- **PyQt5** for the widget toolkit
- **QThread** workers for non-blocking scan operations
- **SQLite** shared database with CLI (same save points DB)
- **QSystemTrayIcon** for tray integration
- **QSS stylesheets** for the Win95 theme

The GUI communicates with the same backend as the CLI — no separate server or API needed. All state is shared through the SQLite database and git repository.

## Requirements

The GUI requires PyQt5, which is included in the pip install but not in the standalone binary. To use the GUI with the binary distribution, install PyQt5 separately:

```bash
pip install pyqt5
```

On headless servers, the GUI is not available. Use CLI or MCP instead.
