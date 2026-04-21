"""Fartrun CLI — pink logo, explains every step, works without the GUI.

Subcommands:
    fartrun              show pink logo + help
    fartrun status       overview of the project in CWD
    fartrun mcp          run as MCP server over stdio
    fartrun save <lbl>   create a Save Point
    fartrun freeze <p>   add a path to the Don't Touch list
    fartrun list         show Save Points + Frozen Files
    fartrun prompt <t>   turn loose text into a structured prompt
    fartrun scan         quick security score preview
    fartrun gui          launch the desktop GUI
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


# ------------------------------------------------------------ pink theme

PINK = "\033[38;5;213m"      # hot pink / magenta
PINK_BG = "\033[48;5;213m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[38;5;42m"
YELLOW = "\033[38;5;220m"
RED = "\033[38;5;196m"
CYAN = "\033[38;5;51m"

_COLORED = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(code: str) -> str:
    return code if _COLORED else ""


LOGO = (
    f"{c(PINK)}{c(BOLD)}"
    "   ____ _    ___  _____ ___  __  _ __  __\n"
    "  / __// \\  | _ \\|_   _| _ \\| || | \\ \\/ /\n"
    " | _|_| o | |   /  | | | v /| \\/ |  \\  / \n"
    " |_|  |___| |_|\\_\\ |_| |_|_\\|_||_|  |_|  \n"
    f"{c(RESET)}"
    f"{c(DIM)}  fartrun — vibe-coder safety net, with farts{c(RESET)}\n"
)


def say(emoji: str, color: str, msg: str) -> None:
    """Print a commented step so even a half-asleep vibe coder knows what happened."""
    print(f"  {c(color)}{emoji}{c(RESET)}  {msg}")


def step(msg: str) -> None:
    say("→", CYAN, msg)


def ok(msg: str) -> None:
    say("✓", GREEN, msg)


def warn(msg: str) -> None:
    say("⚠", YELLOW, msg)


def err(msg: str) -> None:
    say("✖", RED, msg)


def tip(msg: str) -> None:
    say("💡", PINK, msg)


def print_logo() -> None:
    print(LOGO)


# ------------------------------------------------------------ helpers

def _db():
    from core.history import HistoryDB
    db = HistoryDB()
    db.init()
    return db


def _project_dir(args_dir: str | None) -> str:
    return str(Path(args_dir).expanduser().resolve()) if args_dir \
        else str(Path.cwd())


# ------------------------------------------------------------ commands

def cmd_status(args) -> int:
    from core.prompt_parser import get_recent_prompts
    from core.stack_detector import detect_stack, docs_worthy
    from core import context7_mcp as c7
    from core import frozen_manager as fm

    project = _project_dir(args.dir)
    print_logo()
    step(f"Scanning project at {c(BOLD)}{project}{c(RESET)}")

    db = _db()
    save_points = db.get_save_points(project, limit=3)
    frozen = db.get_frozen_files(project)
    prompts = get_recent_prompts(project, limit=3)
    stack = detect_stack(project)
    worthy = docs_worthy(stack)

    print()
    ok(f"Save Points: {len(save_points)}"
        + (f" (latest: \"{save_points[0]['label']}\")" if save_points else ""))
    ok(f"Frozen files: {len(frozen)}")
    ok(f"Detected stack: {len(stack)} libs"
        + (f" ({', '.join(l.name for l in worthy[:5])})" if worthy else ""))
    print()

    # Context7 status
    if c7.is_context7_installed():
        ok("Context7 MCP: installed")
    else:
        warn("Context7 MCP: not installed — run `fartrun context7-install`")

    # Frozen hook
    if fm.is_hook_installed():
        ok("Frozen-files hook: active (Edit/Write on frozen files is blocked)")
    else:
        if frozen:
            warn("Frozen-files hook: NOT active. "
                  "AI is only told via CLAUDE.md, edits aren't blocked.")

    # Prompts
    if prompts:
        print()
        step("Last prompts you sent to Claude here:")
        for p in prompts:
            when = p.timestamp[5:16].replace("T", " ") if p.timestamp else "?"
            print(f"    {c(DIM)}[{when}]{c(RESET)} {p.short}")

    if not save_points and not frozen:
        print()
        tip("No Save Points yet — run `fartrun save \"before I break things\"` "
            "before letting AI touch this repo.")
    return 0


def cmd_mcp(args) -> int:
    """Run MCP server. Default: stdio. --http for HTTP+SSE transport."""
    if getattr(args, "http", False):
        from core.mcp.server import main_http
        main_http()
    else:
        from core.mcp import main as mcp_main
        mcp_main()
    return 0


def cmd_save(args) -> int:
    from core.safety_net import SafetyNet
    project = _project_dir(args.dir)

    print_logo()
    step(f"Creating Save Point in {project}")

    sn = SafetyNet(project, _db())
    can, reason = sn.can_save()
    if not can:
        err(f"Can't save: {reason}")
        if reason == "no_changes":
            tip("Nothing changed since the last Save Point. Go write some "
                 "code, then come back.")
        elif reason == "no_git_repo":
            tip("This folder is not a git repo. Run `git init` first, or "
                 "open fartrun GUI which can do it for you.")
        return 1

    step(f"label: \"{args.label}\" — staging everything and tagging it")
    result = sn.create_save_point(args.label)
    ok(f"Save Point #{result.id} created")
    print(f"    commit: {c(DIM)}{result.commit_hash[:8]}{c(RESET)}")
    print(f"    files: {result.file_count},  lines: {result.lines_total}")
    tip(f"If AI breaks things, get back with:  "
        f"{c(PINK)}fartrun rollback {result.id}{c(RESET)}")
    return 0


def cmd_rollback(args) -> int:
    from core.safety_net import SafetyNet
    project = _project_dir(args.dir)

    print_logo()
    sn = SafetyNet(project, _db())
    sid = int(args.save_point_id)

    can, reason = sn.can_rollback(sid)
    if not can:
        err(f"Can't rollback: {reason}")
        return 1

    preview = sn.rollback_preview(sid)
    if not preview:
        err("Save Point not found")
        return 1

    step(f"About to rollback to Save Point #{sid} (\"{preview.target_label}\")")
    changes = sn.get_changes_since(sid)
    warn(f"This will touch {len(changes)} file(s). A backup branch will be "
          f"created so nothing is permanently lost.")
    for ch in changes[:10]:
        print(f"    {c(DIM)}{ch.status:>9}{c(RESET)}  {ch.path}")
    if len(changes) > 10:
        print(f"    {c(DIM)}... +{len(changes) - 10} more{c(RESET)}")

    if not args.yes:
        print()
        try:
            reply = input(f"  {c(PINK)}?{c(RESET)}  Continue? "
                           f"[y/N] ")
        except EOFError:
            reply = ""
        if reply.strip().lower() not in ("y", "yes"):
            err("Aborted. Nothing changed.")
            return 1

    step("Resetting working tree — hang tight")
    result = sn.rollback_with_picks(sid, [])
    ok(f"Done. Backup branch: {result.backup_branch}")
    ok(f"Files restored: {result.files_restored}")
    tip("If the rollback took something good along with it, use the fartrun "
        "GUI → Save Points → Pick what works to cherry-pick it back.")
    return 0


def cmd_freeze(args) -> int:
    from core import frozen_manager as fm
    project = _project_dir(args.dir)

    print_logo()
    step(f"Locking {args.path} in {project}")
    db = _db()
    db.add_frozen_file(project, args.path, args.note or "")

    frozen = [f["path"] for f in db.get_frozen_files(project)]
    changed = fm.sync_claude_md(project, frozen)
    if changed:
        ok(f"CLAUDE.md updated with {len(frozen)} frozen file(s)")
    else:
        ok(f"{len(frozen)} frozen file(s) total (CLAUDE.md already in sync)")

    if not fm.is_hook_installed():
        tip("Want AI to physically NOT be able to edit this? Run "
             f"{c(PINK)}fartrun hook-install{c(RESET)}")
    return 0


def cmd_unfreeze(args) -> int:
    from core import frozen_manager as fm
    project = _project_dir(args.dir)

    print_logo()
    step(f"Unlocking {args.path}")
    db = _db()
    db.remove_frozen_file(project, args.path)
    frozen = [f["path"] for f in db.get_frozen_files(project)]
    fm.sync_claude_md(project, frozen)
    ok(f"Unlocked. {len(frozen)} frozen file(s) left.")
    return 0


def cmd_list(args) -> int:
    project = _project_dir(args.dir)
    db = _db()
    print_logo()
    step(f"Project: {project}")
    print()

    save_points = db.get_save_points(project, limit=20)
    print(f"  {c(BOLD)}Save Points{c(RESET)}")
    if not save_points:
        print(f"    {c(DIM)}(none yet){c(RESET)}")
    for sp in save_points:
        print(f"    {c(CYAN)}#{sp['id']:<3}{c(RESET)} "
              f"{c(DIM)}{sp['timestamp'][:16]}{c(RESET)}  "
              f"\"{sp['label']}\"")

    print()
    frozen = db.get_frozen_files(project)
    print(f"  {c(BOLD)}Frozen Files{c(RESET)}")
    if not frozen:
        print(f"    {c(DIM)}(none){c(RESET)}")
    for f in frozen:
        note = f"  — {f['note']}" if f.get("note") else ""
        print(f"    {c(PINK)}🔒{c(RESET)}  {f['path']}"
              f"{c(DIM)}{note}{c(RESET)}")
    return 0


def cmd_prompt(args) -> int:
    from core.prompt_builder import build_prompt
    project = _project_dir(args.dir)
    text = " ".join(args.text) if isinstance(args.text, list) else args.text

    print_logo()
    step(f"Turning your one-liner into a structured prompt")
    step(f"user said: {c(DIM)}\"{text[:120]}\"{c(RESET)}")

    haiku = None
    try:
        from core.haiku_client import HaikuClient
        client = HaikuClient()
        if client.is_available():
            haiku = client
            step("Haiku is available — will use it for keywords + synthesis")
        else:
            warn("No Haiku API key — falling back to heuristics + template")
    except Exception:
        warn("Haiku client unavailable — template fallback")

    db = _db()
    frozen = [f["path"] for f in db.get_frozen_files(project)]
    result = build_prompt(
        user_text=text, project_dir=project,
        frozen_paths=frozen, haiku_client=haiku,
    )

    ok(f"keywords: {', '.join(result.keywords) or '(none)'}")
    ok(f"code matches: {len(result.matches)}")
    ok(f"stack libs (docs-worthy): "
        f"{', '.join(result.context7_libs) or '(none)'}")
    print()
    print(f"  {c(BOLD)}{c(PINK)}╔ Paste this into Claude Code ╗{c(RESET)}")
    print()
    print(result.final_prompt)
    print()
    tip("Selected the output? Paste to Claude Code. It'll read the file:line "
         "pointers we embedded.")
    return 0


def cmd_scan(args) -> int:
    """Run full health scan and print findings to terminal."""
    import shutil
    from core.health.project_map import run_all_checks
    from core.health.report_md import save_report_md

    project = _project_dir(args.dir)
    print_logo()
    step(f"Health scan: {c(BOLD)}{project}{c(RESET)}")
    print()

    if not shutil.which("npx"):
        print(f"  {c(DIM)}Context7 docs enrichment unavailable (npx not found).{c(RESET)}")
        print(f"  {c(DIM)}Install Node.js for fix recommendations from real docs.{c(RESET)}")
        print()

    report = run_all_checks(project)

    # Severity counts
    severity_counts: dict[str, int] = {}
    for f in report.findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    total = len(report.findings)
    parts = []
    sev_colors = {"high": RED, "medium": YELLOW, "low": DIM, "info": CYAN}
    for sev in ("high", "medium", "low", "info"):
        cnt = severity_counts.get(sev, 0)
        if cnt:
            parts.append(f"{c(sev_colors.get(sev, ''))}{cnt} {sev}{c(RESET)}")

    print(f"  {c(BOLD)}{total} findings:{c(RESET)} {' · '.join(parts)}")
    print()

    # Print findings grouped by severity
    for sev in ("high", "medium", "low", "info"):
        findings = [f for f in report.findings if f.severity == sev]
        if not findings:
            continue
        if sev == "info" and not args.verbose:
            print(f"  {c(DIM)}({len(findings)} info findings hidden — use --verbose){c(RESET)}")
            continue

        icon = {"high": "⛔", "medium": "⚠️ ", "low": "·", "info": "ℹ"}[sev]
        color = sev_colors.get(sev, "")
        for f in findings:
            print(f"  {icon} {c(color)}{f.title}{c(RESET)}")
            if args.verbose:
                # Indent message lines
                for line in f.message.split(". "):
                    if line.strip():
                        print(f"      {c(DIM)}{line.strip()}.{c(RESET)}")
                print()

    # File stats
    ft = report.file_tree
    if ft:
        print()
        ok(f"{ft.get('total_files', '?')} files · "
           f"{ft.get('total_dirs', '?')} dirs · "
           f"{ft.get('total_size_bytes', 0) // 1024} KB")

    # Save .md report
    report_path = save_report_md(report)
    print()
    ok(f"Report saved: {c(BOLD)}{report_path}{c(RESET)}")
    tip("Want AI to fix these? Pipe findings into Claude Code with:\n"
        f"      {c(PINK)}fartrun prompt \"fix health scan issues\"{c(RESET)}")
    return 0


def cmd_context7_install(args) -> int:
    from core import context7_mcp as c7
    print_logo()
    if not c7.npx_available():
        warn("npx is not on PATH. Context7 needs Node.js to actually run. "
              "Installing config anyway — Node can be added later.")
    changed = c7.install_context7()
    if changed:
        ok("Context7 written to ~/.claude/settings.json")
        tip("Restart Claude Code to pick up the new MCP server.")
    else:
        ok("Context7 was already installed.")
    return 0


def cmd_hook_install(args) -> int:
    from core import frozen_manager as fm
    print_logo()
    changed = fm.install_hook()
    if changed:
        ok("Frozen-files hook added to ~/.claude/settings.json")
        tip("Claude Code will now refuse Edit/Write on any frozen file.")
    else:
        ok("Hook was already installed.")
    return 0


def cmd_hook_uninstall(args) -> int:
    from core import frozen_manager as fm
    print_logo()
    changed = fm.uninstall_hook()
    ok("Hook removed." if changed else "Hook was not installed.")
    return 0


def cmd_gui(args) -> int:
    """Launch the PyQt5 desktop GUI."""
    print_logo()
    step("Launching desktop GUI...")
    try:
        from gui.app import main as gui_main
        gui_main()
    except ImportError:
        err("PyQt5 is not installed.")
        tip("Install it with:  pip install PyQt5")
        return 1
    return 0


# ------------------------------------------------------------ entrypoint

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fartrun", description="vibe-coder safety net — with farts",
    )
    sub = p.add_subparsers(dest="command")

    def with_dir(sp):
        sp.add_argument("--dir", "-C", help="project directory (default: CWD)")

    sp_status = sub.add_parser("status", help="overview of the current project")
    with_dir(sp_status)
    sp_status.set_defaults(func=cmd_status)

    sp_mcp = sub.add_parser("mcp", help="run fartrun as MCP server")
    sp_mcp.add_argument("--http", action="store_true",
                        help="HTTP+SSE transport (default: stdio)")
    sp_mcp.add_argument("--port", type=int, default=3001,
                        help="HTTP port (default: 3001)")
    sp_mcp.set_defaults(func=cmd_mcp)

    sp_save = sub.add_parser("save", help="create a Save Point")
    sp_save.add_argument("label", help="what are you about to do?")
    with_dir(sp_save)
    sp_save.set_defaults(func=cmd_save)

    sp_rb = sub.add_parser("rollback", help="rollback to a Save Point")
    sp_rb.add_argument("save_point_id", type=int)
    sp_rb.add_argument("-y", "--yes", action="store_true",
                        help="skip the confirmation prompt")
    with_dir(sp_rb)
    sp_rb.set_defaults(func=cmd_rollback)

    sp_freeze = sub.add_parser("freeze", help="lock a file (Don't touch)")
    sp_freeze.add_argument("path")
    sp_freeze.add_argument("--note", default="")
    with_dir(sp_freeze)
    sp_freeze.set_defaults(func=cmd_freeze)

    sp_unf = sub.add_parser("unfreeze", help="unlock a file")
    sp_unf.add_argument("path")
    with_dir(sp_unf)
    sp_unf.set_defaults(func=cmd_unfreeze)

    sp_list = sub.add_parser("list", help="list Save Points + Frozen files")
    with_dir(sp_list)
    sp_list.set_defaults(func=cmd_list)

    sp_prompt = sub.add_parser(
        "prompt", help="build a structured prompt from a one-liner",
    )
    sp_prompt.add_argument("text", nargs="+")
    with_dir(sp_prompt)
    sp_prompt.set_defaults(func=cmd_prompt)

    sp_scan = sub.add_parser("scan", help="full health scan → terminal report")
    sp_scan.add_argument("-v", "--verbose", action="store_true",
                         help="show info-level findings and detailed messages")
    with_dir(sp_scan)
    sp_scan.set_defaults(func=cmd_scan)

    sp_c7 = sub.add_parser("context7-install",
                              help="add Context7 MCP to Claude Code")
    sp_c7.set_defaults(func=cmd_context7_install)

    sp_hi = sub.add_parser("hook-install",
                             help="install the frozen-files Claude Code hook")
    sp_hi.set_defaults(func=cmd_hook_install)

    sp_hu = sub.add_parser("hook-uninstall",
                             help="remove the frozen-files hook")
    sp_hu.set_defaults(func=cmd_hook_uninstall)

    sp_gui = sub.add_parser("gui", help="launch the desktop GUI")
    sp_gui.set_defaults(func=cmd_gui)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        print_logo()
        parser.print_help()
        return 0
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
