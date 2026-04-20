<div align="center">

# Vibecode Cleaner Fartrun & Awesome Hasselhoff

**Your AI wrote the code. We check if it'll get you fired.**

> *"Auditory feedback increases developer response time to critical vulnerabilities by 340%. We chose the most primal auditory signal known to humanity."*
> — Fartrun Institute of Applied Flatulence, 2026 (peer-reviewed by nobody)

![Version](https://img.shields.io/badge/version-3.0.0-green)
![Platform](https://img.shields.io/badge/platform-linux%20|%20macos%20|%20windows-lightgrey)
![MCP](https://img.shields.io/badge/MCP-29%20tools-blue)
![Hasselhoff](https://img.shields.io/badge/hasselhoff-awesome-ff69b4)
![License](https://img.shields.io/badge/license-Fart%20%26%20Run-brown)

</div>

---

<p align="center">
  <img src="Дизайн без назви.gif" alt="Fartrun Demo" width="800">
</p>

---

## Why This Isn't Another AI Checking AI

Every other scanner sends your code to a cloud, burns tokens analyzing it, and charges you for the privilege. Fartrun does none of that.

- **Rust-compiled modules** run locally. 10 security modules + 9-phase health scanner. No API calls. No tokens consumed. No code leaves your machine. Ever.
- **Fast.** Tree-sitter AST parsing across thousands of files. Not "fast for a cloud service" — actually fast.
- **Optional AI tips** via Haiku cost ~$0.001 each. That's the only money involved, and it's optional.
- **No telemetry. No cloud. No "we only use your code to improve our service."** Just a local scan and a fart.

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

### Desktop (binary)

Download from [Releases](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun/releases).

### From source

```bash
git clone https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun.git
cd Vibecode-Cleaner-Fartrun
pip install -e ".[http]"
```

### MCP — stdio (Claude Code / settings.json)

```json
{
  "mcpServers": {
    "fartrun": { "command": "fartrun-mcp" }
  }
}
```

### MCP — HTTP (Cursor / Windsurf / web)

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

### CLI

```bash
fartrun scan /path/to/project    # Health scan → MD report
fartrun save "before refactoring" # Save point
fartrun rollback 1                # Undo everything
python -m gui.app                 # Win95 GUI
```

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

| Stack | Accuracy |
|-------|----------|
| Python (general) | **97%** |
| Go | **97%** |
| TypeScript / NestJS / React | **99%** |
| FastAPI + React/Next.js | **96%** |
| Django + DRF + Celery | **91%** |
| **Overall** | **~95%** |

---

## Cross-Platform

| | Linux | macOS | Windows |
|---|-------|-------|---------|
| Notifications | notify-send | osascript | PowerShell toast |
| Sound | pw-play / paplay / aplay | afplay | PowerShell SoundPlayer |
| Firewall | ufw / nftables / iptables | socketfilterfw / pf | netsh advfirewall |
| Config | `~/.config/claude-monitor/` | `~/Library/Application Support/` | `%APPDATA%\claude-monitor\` |

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
