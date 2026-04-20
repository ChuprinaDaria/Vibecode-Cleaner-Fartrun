<div align="center">

# Vibecode Cleaner Fartrun & Awesome Hasselhoff

**Your AI wrote the code. We check if it'll get you fired.**

> *"Auditory feedback increases developer response time to critical vulnerabilities by 340%. We chose the most primal auditory signal known to humanity."*
> — Fartrun Institute of Applied Flatulence, 2026 (peer-reviewed by nobody)

![Version](https://img.shields.io/badge/version-3.0.0-green)
![Platform](https://img.shields.io/badge/platform-linux%20|%20macos%20|%20windows-lightgrey)
![MCP](https://img.shields.io/badge/MCP-29%20tools-blue)
![Bilingual](https://img.shields.io/badge/lang-EN%20|%20UA-yellow)
![Hasselhoff](https://img.shields.io/badge/hasselhoff-awesome-ff69b4)
![License](https://img.shields.io/badge/license-Fart%20%26%20Run-brown)
[![GitHub stars](https://img.shields.io/github/stars/ChuprinaDaria/Vibecode-Cleaner-Fartrun?style=social)](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun)

</div>

---

<p align="center">
  <img src="Дизайн без назви.gif" alt="Fartrun Demo" width="800">
</p>

---

## Why This Isn't Another AI Checking AI

If you're vibe coding with Claude, Cursor, or Copilot and have no idea what just got committed to your repo — Fartrun finds the problems before your team lead does.

Every other scanner sends your code to a cloud, burns tokens analyzing it, and charges you for the privilege. Fartrun does none of that.

- **Rust-compiled modules** run locally. 10 security modules + 9-phase health scanner. No API calls. No tokens consumed. No code leaves your machine. Ever.
- **Fast.** Tree-sitter AST parsing across thousands of files. Not "fast for a cloud service" — actually fast.
- **Optional AI tips** via Haiku cost ~$0.001 each. That's the only money involved, and it's optional.
- **No telemetry. No cloud. No "we only use your code to improve our service."** Just a local scan and a fart.
- **Bilingual.** All findings, nag messages, and the GUI speak both English and Ukrainian.

---

## Real-World Example

Here's what Fartrun found on a real vibe-coded Django + React project (62 files, built entirely with AI assistants):

```
┌─────────────────────────────────────────────────────────┐
│  fartrun scan ~/atbalance                               │
│                                                         │
│  51 findings: 3 high · 26 medium · 9 low · 13 info     │
│                                                         │
│  HIGH:                                                  │
│  ⛔ No tests found — zero test files in the project     │
│  ⛔ DEBUG defaults to True in settings.py               │
│  ⛔ backend/venv/ tracked by git (7167 files!)          │
│                                                         │
│  MEDIUM (selected):                                     │
│  ⚠️  SECRET_KEY falls back to insecure default          │
│  ⚠️  npm install without lockfile in Dockerfile         │
│  ⚠️  No API throttling — bots will hammer your forms    │
│  ⚠️  :latest tags in docker-compose.prod.yml            │
│  ⚠️  import * from react-icons in 2 components         │
│  ⚠️  11 unused imports and dead classes                 │
│  ⚠️  Copy-paste: CookiePolicy ↔ PrivacyPolicy (26 ln)  │
│                                                         │
│  Time: 0.8s · No tokens burned · No code uploaded       │
└─────────────────────────────────────────────────────────┘
```

The AI built it. The AI didn't mention any of this. Fartrun did.

---

## What It Does

| Feature | Details |
|---------|---------|
| **Security Scanner** | 10 Rust modules — processes, network, filesystem, secrets, supply chain, git hooks, container escape, autostart, crontab, env leak |
| **Health Scanner** | 9-phase project audit — dead code, tech debt, test coverage, git hygiene, docs quality, framework checks, Context7 fix recommendations |
| **Token Monitor** | Tracks Claude Code spending, cache efficiency, model comparison, budget forecasts. Reads your JSONL diaries. Locally. Judges silently. |
| **MCP Server** | 29 tools, stdio + HTTP/SSE. Works with Claude Code, Cursor, Windsurf, any MCP client |
| **Context7 Enrichment** | Findings get real documentation snippets — not "add tests" but the actual pytest Getting Started guide |
| **Nag Messages** | 4 escalation levels in EN/UA. From *"Tokens: 45K. Calories burned: 0."* to *"GG. 1.2M tokens. Touch grass."* |
| **Win95 GUI** | PyQt5 desktop app. 8 pages. Popup notifications. Hasselhoff wizard. Peak aesthetic. |

---

## Quick Start

### 1. Download Binary (fastest)

Grab the latest release for your OS:

| OS | File | Install |
|----|------|---------|
| **Linux** | `fartrun-linux-x64.tar.gz` | `tar xzf fartrun-linux-x64.tar.gz && chmod +x fartrun` |
| **macOS** | `fartrun-macos-x64.zip` | `unzip fartrun-macos-x64.zip` |
| **Windows** | `fartrun-windows-x64.zip` | Extract zip |

**[Download from Releases →](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun/releases)**

Then run:
```bash
./fartrun scan /path/to/project
```

<details>
<summary><b>Platform-specific notes</b></summary>

#### Linux

```bash
tar xzf fartrun-linux-x64.tar.gz
chmod +x fartrun
./fartrun scan /path/to/project

# Optional: global install
sudo mv fartrun /usr/local/bin/
```

#### macOS

```bash
unzip fartrun-macos-x64.zip

# If you got Fartrun.app:
open Fartrun.app
# CLI access:
./Fartrun.app/Contents/MacOS/fartrun scan /path/to/project

# If standalone binary:
chmod +x fartrun
./fartrun scan /path/to/project
```

> **Gatekeeper:** macOS may block unsigned apps. Run once:
> ```bash
> xattr -d com.apple.quarantine fartrun
> ```
> Signed & notarized builds coming soon.

#### Windows

1. Extract `fartrun-windows-x64.zip`
2. Open PowerShell in the extracted folder
3. Run:
```powershell
.\fartrun.exe scan C:\path\to\project
```

> **SmartScreen:** Windows may show "Unknown publisher". Click "More info" → "Run anyway". Code-signed builds coming soon.

</details>

<details>
<summary><b>From source</b></summary>

```bash
git clone https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun.git
cd Vibecode-Cleaner-Fartrun
pip install -e ".[http]"
```

</details>

### 2. MCP — stdio (Claude Code)

```json
{
  "mcpServers": {
    "fartrun": { "command": "fartrun-mcp" }
  }
}
```

### 3. MCP — HTTP (Cursor / Windsurf / web)

```bash
fartrun mcp --http --port 3001
```

```json
{
  "mcpServers": {
    "fartrun": { "url": "http://localhost:3001/sse" }
  }
}
```

### 4. CLI

```bash
fartrun scan /path/to/project    # Health scan → MD report
fartrun save "before refactoring" # Save point
fartrun rollback 1                # Undo everything
python -m gui.app                 # Win95 GUI
```

---

## Fartrun vs Cloud Scanners

| | **Fartrun** | Snyk | SonarQube | Semgrep Cloud |
|---|---|---|---|---|
| Runs locally | Yes | No | Self-host option | No |
| Code leaves your machine | Never | Yes | Depends | Yes |
| Free | Forever | Freemium | Freemium | Freemium |
| AI vibe-code specific checks | Yes | No | No | No |
| Scan time (1K files) | <2s | 30-60s | 20-40s | 10-20s |
| Setup time | 0 (binary) | Account + CLI | Server + config | Account + CLI |
| Fart sounds | Yes | No | No | No |
| Hasselhoff | Yes | No | No | No |

---

## MCP Tools (29)

| Category | Tools |
|----------|-------|
| **Health** | `run_health_scan`, `get_health_summary`, `get_unused_code`, `get_tech_debt`, `get_security_issues`, `get_module_graph`, `get_complexity_report`, `get_git_health`, `get_test_coverage`, `get_docs_quality`, `get_ui_issues`, `get_framework_check`, `get_outdated_deps`, `get_config_map`, `generate_health_report` |
| **Status** | `get_status`, `get_activity`, `detect_project_stack`, `search_code` |
| **Prompts** | `build_prompt` |
| **Save Points** | `create_save_point`, `rollback_save_point`, `list_save_points` |
| **Frozen Files** | `freeze_file`, `unfreeze_file`, `list_frozen` |
| **Integrations** | `install_context7`, `uninstall_context7`, `list_prompts` |

---

## Farts & Hasselhoff

| Severity | Classic | Fart Mode | What it means |
|----------|---------|-----------|---------------|
| Critical | Air raid siren | The Devastator | Your secrets are already on Pastebin |
| High | Alarm bell | The Thunderclap | Someone will find this. Soon. |
| Medium | Warning beep | The Squeaker | Not great, not terrible |
| Low | Gentle ping | The Whisper | Technically a finding. Relax. |
| Info | Soft chime | The Silent But Deadly | Good to know. Carry on. |

Hasselhoff used to appear for everything. Container started? Hasselhoff. You blinked? Hasselhoff. Beta testers staged an intervention. Now he only shows up when summoned. He's still watching though.

---

## Health Scanner Accuracy

Tested on 12 real projects across 6 stacks:

| Stack | Example project | Accuracy |
|-------|----------------|----------|
| Python (general) | Flask REST API, CLI tools | **97%** |
| Go | gRPC microservice | **97%** |
| TypeScript / NestJS / React | SaaS dashboard | **99%** |
| FastAPI + React/Next.js | AI chatbot with RAG | **96%** |
| Django + DRF + Celery | Business CRM, landing pages | **91%** |
| **Overall** | | **~95%** |

---

## Cross-Platform

| | Linux | macOS | Windows |
|---|-------|-------|---------|
| Notifications | notify-send | osascript | PowerShell toast |
| Sound | pw-play / paplay / aplay | afplay | PowerShell SoundPlayer |
| Firewall | ufw / nftables / iptables | socketfilterfw / pf | netsh advfirewall |
| Config | `~/.config/claude-monitor/` | `~/Library/Application Support/` | `%APPDATA%\claude-monitor\` |

---

## Star If It Saved You Once

That's it. Stars = visibility = more people not getting fired.

[![GitHub stars](https://img.shields.io/github/stars/ChuprinaDaria/Vibecode-Cleaner-Fartrun?style=social)](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun)

---

## Buy Me a Toilet Paper

This project is free. Forever. No premium tier. No "enterprise edition."

If Fartrun saved you from mass embarrassment:

[![Buy Me a Toilet Paper](https://img.shields.io/badge/donate-toilet%20paper-yellow)](https://buy.stripe.com/8x228r3p3dYL3TFebC5gc0b)

All donations go toward toilet paper, coffee, and finding the perfect fart sound for the next severity level.

---

## Made By

**Daria Chuprina** — [Lazysoft](https://lazysoft.pl), Wroclaw

[LinkedIn](https://www.linkedin.com/in/dchuprina/) · [GitHub](https://github.com/ChuprinaDaria) · [Threads](https://www.threads.com/@sonya_orehovaya) · [Reddit](https://www.reddit.com/user/Illustrious_Grass534/) · [Email](mailto:dchuprina@lazysoft.pl)

---

## Contributing

PRs welcome. Especially: better fart sounds (WAV/OGG, royalty-free, funny), new Rust sentinel modules, Hasselhoff facts, nag message translations (maximum passive-aggression encouraged), security courses for your country.

---

## Fart & Run License

```
FART & RUN LICENSE v1.0 — Copyright (c) 2026 Daria Chuprina

1. You may fart and run, but you must attribute the original farter.
2. You may not mass-fart on production servers you don't own.
3. THE SOFTWARE IS PROVIDED "AS IS". If it misses a vulnerability,
   that's on you for trusting a scanner named after flatulence.
4. Hasselhoff appearances are AS-AVAILABLE, not guaranteed.
5. Nag messages are a feature. Disabling them voids your warranty
   (you never had one).
6. The "Silent But Deadly" mode is exactly what it sounds like.
   And doesn't sound like.
```

---

<p align="center">
  <i>Made with flatulence in Wroclaw, Poland</i>
</p>
