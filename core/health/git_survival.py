"""Git Survival checks — git status explainer, commit quality, branch awareness, gitignore health, cheat sheet."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from core.health.models import HealthFinding, HealthReport
from core.health.git_utils import run_git as _run_git, is_git_repo as _is_git_repo

log = logging.getLogger(__name__)


@dataclass
class GitStatusCounts:
    """Structured breakdown of `git status --porcelain=v1` output.

    Each list holds distinct filenames. A file with combined status
    (e.g. `MM`) can appear in both `staged` and `modified`; `total`
    counts distinct files so the sum reconciles with the raw line count.
    """
    staged: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    renamed: list[str] = field(default_factory=list)
    unmerged: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Distinct files reported, matching `git status --porcelain` line count."""
        seen: set[str] = set()
        for bucket in (
            self.staged, self.modified, self.deleted,
            self.untracked, self.renamed, self.unmerged,
        ):
            for f in bucket:
                seen.add(f)
        return len(seen)


def parse_git_status_porcelain(output: str) -> GitStatusCounts:
    """Parse `git status --porcelain=v1` output into structured counts.

    Format: `XY path` where X is index status, Y is work-tree status.
    Classification table:

    | X              | Y    | bucket                            |
    |----------------|------|-----------------------------------|
    | `?`            | `?`  | untracked                         |
    | any of AMDRCT  | ` `  | staged                            |
    | any of AMDRCT  | M/T  | staged + modified                 |
    | ` `            | M/T  | modified                          |
    | ` `            | D    | deleted (unstaged)                |
    | R              | any  | renamed (staged rename)           |
    | U / any+U      | any  | unmerged                          |
    """
    counts = GitStatusCounts()
    for line in output.splitlines():
        if not line or len(line) < 3:
            continue
        x, y = line[0], line[1]
        filename = line[3:]

        if x == "?" and y == "?":
            counts.untracked.append(filename)
            continue
        if x == "U" or y == "U":
            counts.unmerged.append(filename)
            continue
        if x == "R":
            # staged rename — includes `old -> new` in path
            counts.renamed.append(filename)
            if y in {"M", "T"}:
                counts.modified.append(filename)
            continue

        # Index column: staged state
        if x in {"A", "M", "D", "C", "T"}:
            counts.staged.append(filename)
        # Work-tree column: unstaged state on top
        if y == "M" or y == "T":
            counts.modified.append(filename)
        elif y == "D" and x == " ":
            counts.deleted.append(filename)
        elif y == "R" and x == " ":
            counts.renamed.append(filename)

    return counts


def check_git_status(report: HealthReport, project_dir: str) -> None:
    """Check 5.1 — explain git status in human language."""
    if not _is_git_repo(project_dir):
        report.findings.append(HealthFinding(
            check_id="git.status",
            title="Not a git repository",
            severity="medium",
            message=(
                "This directory is not tracked by git. "
                "Run 'git init' to start version control. "
                "Without git, you can't undo mistakes."
            ),
        ))
        return

    output = _run_git(project_dir, "status", "--porcelain")
    if not output:
        report.findings.append(HealthFinding(
            check_id="git.status",
            title="Git: clean working tree",
            severity="info",
            message="Everything is committed. Clean slate.",
        ))
        return

    c = parse_git_status_porcelain(output)

    parts: list[str] = []
    if c.staged:
        parts.append(f"{len(c.staged)} staged (ready to commit)")
    if c.modified:
        parts.append(f"{len(c.modified)} modified (changed but not staged)")
    if c.deleted:
        parts.append(f"{len(c.deleted)} deleted (not staged)")
    if c.renamed:
        parts.append(f"{len(c.renamed)} renamed")
    if c.unmerged:
        parts.append(f"{len(c.unmerged)} unmerged (conflict)")
    if c.untracked:
        parts.append(f"{len(c.untracked)} untracked (new files git doesn't know about)")

    report.findings.append(HealthFinding(
        check_id="git.status",
        title=f"Git status: {', '.join(parts)}",
        severity="info",
        message=(
            f"Working tree: {', '.join(parts)}. "
            + ("Staged files are ready for commit. " if c.staged else "")
            + ("Modified files need 'git add' before commit. " if c.modified else "")
            + ("Deleted files need 'git add' (or 'git restore') to stage the deletion. " if c.deleted else "")
            + ("Unmerged files block further work — resolve conflicts first. " if c.unmerged else "")
            + ("Untracked files won't be saved until you 'git add' them." if c.untracked else "")
        ),
    ))


def _is_shallow_clone(project_dir: str) -> bool:
    """Detect shallow git clones (e.g. git clone --depth 1).
    In a shallow clone, the initial commit contains the entire history
    squashed, which trips the "big commit" heuristic with false positives.
    """
    from pathlib import Path
    return (Path(project_dir) / ".git" / "shallow").exists()


def check_commit_quality(report: HealthReport, project_dir: str) -> None:
    """Check 5.2 — check recent commits for size and message quality."""
    if not _is_git_repo(project_dir):
        return

    log_output = _run_git(
        project_dir, "log", "--oneline", "--shortstat", "-10"
    )
    if not log_output:
        return

    is_shallow = _is_shallow_clone(project_dir)

    bad_messages = ["fix", "update", "wip", "test", "asdf", ".", "temp", "stuff", "changes"]
    big_commits = []
    bad_msg_commits = []

    lines = log_output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Oneline: "abc1234 message"
        parts = line.split(" ", 1)
        if len(parts) < 2:
            i += 1
            continue

        commit_hash = parts[0]
        message = parts[1].strip().lower()

        # Check message quality
        if message in bad_messages or len(message) < 4:
            bad_msg_commits.append((commit_hash, parts[1].strip()))

        # Check next line for stats
        if i + 1 < len(lines):
            stat_line = lines[i + 1].strip()
            if "file" in stat_line and "changed" in stat_line:
                # Parse "N files changed, M insertions(+), K deletions(-)"
                try:
                    insertions = 0
                    deletions = 0
                    if "insertion" in stat_line:
                        ins_part = stat_line.split("insertion")[0].split(",")[-1].strip()
                        insertions = int(ins_part)
                    if "deletion" in stat_line:
                        del_part = stat_line.split("deletion")[0].split(",")[-1].strip()
                        deletions = int(del_part)
                    total = insertions + deletions
                    if total > 300:
                        # Shallow clones (--depth N) squash the earliest
                        # visible commit with all the history before it —
                        # skip those to avoid a guaranteed false positive.
                        is_oldest_visible = (i + 2 >= len(lines))
                        if is_shallow and is_oldest_visible and total > 100_000:
                            pass
                        else:
                            big_commits.append((commit_hash, parts[1].strip(), total))
                except (ValueError, IndexError):
                    pass
                i += 2
                continue

        i += 1

    if big_commits:
        for commit_hash, msg, total in big_commits[:3]:
            report.findings.append(HealthFinding(
                check_id="git.commits",
                title=f"Big commit: {commit_hash} ({total} lines)",
                severity="low",
                message=(
                    f"Commit '{msg}' changed {total} lines. "
                    f"That's not a commit, that's a release. "
                    f"Small commits = easy rollback."
                ),
            ))

    if bad_msg_commits:
        for commit_hash, msg in bad_msg_commits[:3]:
            report.findings.append(HealthFinding(
                check_id="git.commits",
                title=f"Vague commit: '{msg}'",
                severity="low",
                message=(
                    f"Commit '{msg}' — what does this mean in 2 weeks? "
                    f"Good format: 'feat: add user login' or 'fix: crash on empty input'."
                ),
            ))


def check_branch_awareness(report: HealthReport, project_dir: str) -> None:
    """Check 5.3 — current branch, unmerged branches, direct main commits."""
    if not _is_git_repo(project_dir):
        return

    branch = _run_git(project_dir, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"

    # Check if committing directly to main/master
    if branch in ("main", "master"):
        # Count recent commits on main
        log_output = _run_git(project_dir, "log", "--oneline", "-5")
        commit_count = len(log_output.splitlines()) if log_output else 0

        if commit_count > 0:
            report.findings.append(HealthFinding(
                check_id="git.branches",
                title=f"Working directly on {branch}",
                severity="low",
                message=(
                    f"You're on '{branch}' and committing directly. "
                    f"That's like editing the original document without a copy. "
                    f"Create a branch: git checkout -b my-feature"
                ),
            ))

    # Count unmerged branches
    branches_output = _run_git(project_dir, "branch", "--no-merged")
    if branches_output:
        unmerged = [b.strip().lstrip("* ") for b in branches_output.splitlines() if b.strip()]
        if unmerged:
            report.findings.append(HealthFinding(
                check_id="git.branches",
                title=f"{len(unmerged)} unmerged branches",
                severity="info",
                message=(
                    f"Branches not merged: {', '.join(unmerged[:5])}. "
                    + (f"(and {len(unmerged) - 5} more) " if len(unmerged) > 5 else "")
                    + "Merge or delete them to keep things clean."
                ),
            ))


def check_gitignore(report: HealthReport, project_dir: str) -> None:
    """Check 5.4 — .gitignore existence and completeness."""
    root = Path(project_dir)
    gitignore = root / ".gitignore"

    # Collect content from root .gitignore AND subdirectory .gitignore files
    all_content_parts: list[str] = []
    if gitignore.exists():
        try:
            all_content_parts.append(gitignore.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass

    # Check up to 2 levels deep for sub-gitignores (e.g. backend/.gitignore)
    from core.health import _SKIP_DIRS
    for child in root.iterdir():
        if not child.is_dir() or child.name in _SKIP_DIRS:
            continue
        sub_gi = child / ".gitignore"
        if sub_gi.exists():
            try:
                all_content_parts.append(sub_gi.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass

    if not all_content_parts:
        report.findings.append(HealthFinding(
            check_id="git.gitignore",
            title="No .gitignore file",
            severity="medium",
            message=(
                "No .gitignore — you might be committing junk files. "
                "Create one: https://gitignore.io or 'npx gitignore node' / 'npx gitignore python'."
            ),
        ))
        return

    content = "\n".join(all_content_parts)

    # Check for common missing patterns
    missing = []

    # Detect project type and check relevant patterns
    from core.health import has_files_with_ext
    has_python = has_files_with_ext(root, "py")
    has_node = (root / "package.json").exists()

    if has_python:
        checks = {
            "__pycache__": "__pycache__/",
            ".venv": ".venv/ or venv/",
            "*.pyc": "*.pyc",
        }
        for pattern, desc in checks.items():
            if pattern not in content:
                missing.append(desc)

    if has_node:
        if "node_modules" not in content:
            missing.append("node_modules/")
        if ".next" not in content and (root / ".next").exists():
            missing.append(".next/")

    # Universal
    if ".env" not in content and any(root.glob(".env*")):
        missing.append(".env (secrets!)")
    if ".DS_Store" not in content:
        missing.append(".DS_Store")

    if missing:
        report.findings.append(HealthFinding(
            check_id="git.gitignore",
            title=f".gitignore missing: {', '.join(missing[:3])}",
            severity="medium" if ".env" in str(missing) else "low",
            message=(
                f".gitignore is missing: {', '.join(missing)}. "
                f"Without these, you might commit secrets or 40,000 node_modules files."
            ),
        ))


def generate_cheat_sheet(report: HealthReport, project_dir: str) -> None:
    """Check 5.5 — context-sensitive git commands based on current state."""
    if not _is_git_repo(project_dir):
        report.findings.append(HealthFinding(
            check_id="git.cheatsheet",
            title="Git quick start",
            severity="info",
            message="git init → git add . → git commit -m 'first commit'. Three commands. Done.",
        ))
        return

    commands = []

    status = _run_git(project_dir, "status", "--porcelain")
    if status:
        has_untracked = any(l.startswith("??") for l in status.splitlines() if l.strip())
        has_modified = any(l[1] == "M" for l in status.splitlines() if len(l) > 1)
        has_staged = any(l[0] in "AMDRC" for l in status.splitlines() if l.strip())

        if has_untracked:
            commands.append("git add <file> — start tracking a new file")
        if has_modified:
            commands.append("git add <file> — stage your changes for commit")
        if has_staged:
            commands.append("git commit -m 'description' — save staged changes")
        if has_modified or has_untracked:
            commands.append("git stash — temporarily hide changes, work on something else")
    else:
        commands.append("git log --oneline -5 — see recent history")
        commands.append("git diff — see what changed since last commit")

    branch = _run_git(project_dir, "rev-parse", "--abbrev-ref", "HEAD") or ""
    if branch in ("main", "master"):
        commands.append(f"git checkout -b my-feature — create a branch before changing {branch}")

    if commands:
        cmd_text = " | ".join(commands[:4])
        report.findings.append(HealthFinding(
            check_id="git.cheatsheet",
            title="Git commands you need right now",
            severity="info",
            message=cmd_text,
        ))


def run_git_survival_checks(report: HealthReport, project_dir: str) -> None:
    """Run all git survival checks."""
    check_git_status(report, project_dir)
    check_commit_quality(report, project_dir)
    check_branch_awareness(report, project_dir)
    check_gitignore(report, project_dir)
    generate_cheat_sheet(report, project_dir)
