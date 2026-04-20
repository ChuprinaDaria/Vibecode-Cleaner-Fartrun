# Cross-Platform Support

Fartrun runs on Linux, macOS, and Windows. This page documents platform-specific behavior, file paths, and known quirks.

## Binary Distribution

Pre-built binaries are published on GitHub Releases for each platform:

| Platform | Binary | Architecture |
|----------|--------|-------------|
| Linux | `fartrun-linux-x86_64` | x86_64 |
| Linux | `fartrun-linux-aarch64` | ARM64 |
| macOS | `fartrun-macos-x86_64` | Intel |
| macOS | `fartrun-macos-aarch64` | Apple Silicon |
| Windows | `fartrun-windows-x86_64.exe` | x86_64 |

The npm installer (`npx fartrun@latest install`) auto-detects platform and architecture to download the correct binary.

## File Paths

### Config File

| OS | Path |
|----|------|
| Linux | `~/.config/fartrun/config.toml` |
| macOS | `~/Library/Application Support/fartrun/config.toml` |
| Windows | `%APPDATA%\fartrun\config.toml` |

### Data Directory (save points, cache, logs)

| OS | Path |
|----|------|
| Linux | `~/.local/share/fartrun/` |
| macOS | `~/Library/Application Support/fartrun/` |
| Windows | `%LOCALAPPDATA%\fartrun\` |

### MCP Client Config

| Client | OS | Config Path |
|--------|----|-------------|
| Claude Code | All | `~/.claude/settings.json` |
| Cursor | All | `~/.cursor/mcp.json` |
| Windsurf | All | `~/.windsurf/mcp.json` |

On Windows, `~` resolves to `%USERPROFILE%`.

## Notifications

### Linux

Uses `notify-send` (libnotify). Falls back to printing to stderr if not available.

Requires a running notification daemon (GNOME, KDE, and most desktop environments include one). On headless servers, notifications are silently skipped.

### macOS

Uses `osascript` to display native macOS notifications:
```bash
osascript -e 'display notification "message" with title "fartrun"'
```

No additional dependencies required. Works on all macOS versions 10.14+.

### Windows

Uses PowerShell toast notifications via BurntToast module if available, falls back to balloon tips via System.Windows.Forms.

## Sound Playback

### Linux

Player detection order:
1. `paplay` (PulseAudio/PipeWire) — most modern Linux desktops
2. `aplay` (ALSA) — fallback for minimal setups
3. `mpv` — if installed
4. `ffplay` — if FFmpeg is installed

Volume control uses `pactl` for PulseAudio or the player's built-in volume flag.

### macOS

Uses `afplay`, which is always present on macOS. Volume controlled via `-v` flag:
```bash
afplay -v 0.7 /path/to/sound.wav
```

### Windows

Uses .NET `SoundPlayer` via PowerShell:
```powershell
(New-Object Media.SoundPlayer "C:\path\to\sound.wav").PlaySync()
```

## Security Scanner Platform Differences

Most sentinel modules work identically across platforms. Exceptions:

### Autostart Module

| OS | What It Checks |
|----|---------------|
| Linux | systemd unit files, XDG autostart, cron `@reboot` |
| macOS | LaunchAgents, LaunchDaemons, login items |
| Windows | Registry Run/RunOnce keys, Startup folder, Task Scheduler |

### Crontab Module

| OS | What It Checks |
|----|---------------|
| Linux | `/etc/crontab`, user crontabs, systemd timers |
| macOS | crontabs, launchd plists with `StartCalendarInterval` |
| Windows | Task Scheduler XML exports |

### Container Escape Module

Docker Desktop on macOS and Windows runs containers in a Linux VM, so host path mounts and socket access have different security implications than on native Linux. The scanner accounts for this in its severity ratings.

## macOS Gatekeeper

The macOS binary is code-signed with an Apple Developer ID certificate and notarized through Apple's notarization service. This means:

- No Gatekeeper warnings on first launch
- No need to right-click and "Open" to bypass security
- The binary passes `spctl --assess` verification

If you build from source, the resulting binary will not be signed. macOS will show "unidentified developer" warning. To bypass:
```bash
xattr -d com.apple.quarantine /path/to/fartrun
```

## Windows SmartScreen

The Windows binary is not currently code-signed with an EV certificate, so SmartScreen may show a warning on first run. Users need to click "More info" then "Run anyway".

This warning disappears after enough users run the binary and it builds reputation with Microsoft's SmartScreen filter.

## Shell Integration

### Linux/macOS

Add to `~/.bashrc` or `~/.zshrc`:
```bash
eval "$(fartrun completions bash)"   # or zsh
```

### Windows (PowerShell)

```powershell
fartrun completions powershell | Out-String | Invoke-Expression
```

Add to your PowerShell profile (`$PROFILE`) for persistence.

## Known Platform Issues

| Issue | Platform | Workaround |
|-------|----------|------------|
| GUI crashes on Wayland | Linux | Set `QT_QPA_PLATFORM=xcb` |
| Tray icon missing on GNOME 44+ | Linux | Install `gnome-shell-extension-appindicator` |
| Sound not playing in WSL | Windows/WSL | Use native Windows binary, not WSL |
| `afplay` blocks terminal | macOS | Sounds play in background thread, not affected in normal usage |
| Long paths (>260 chars) | Windows | Enable long paths in Group Policy or registry |
| PyQt5 DPI scaling | Windows | Set `QT_SCALE_FACTOR=1` for consistent sizing |
