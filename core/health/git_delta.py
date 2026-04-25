"""Compute file deltas between commits and find cache anchors.

Primitives for incremental ("blast-radius") scans:

- `changed_files_since(project_dir, since_hash)` — list of paths touched
  between an earlier commit and HEAD.
- `find_ancestor_cache_hash(project_dir)` — the most recent ancestor of HEAD
  that has a cached report, so a delta scan can re-use that report and only
  re-scan what changed since.

These are pure helpers — they do not run scanners or mutate the cache.
The orchestrator wires them together once Rust per-file scanner APIs are
available; until then, callers can use these to inspect what *would* be
re-scanned in a delta run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.health import cache
from core.health.git_utils import is_git_repo, run_git

log = logging.getLogger(__name__)


# Status letters returned by `git diff --name-status` that we recognise.
# A=added, M=modified, R=renamed, C=copied, D=deleted, T=type-changed.
# We treat R/C as both "old path deleted" and "new path added".
@dataclass(frozen=True)
class FileChange:
    status: str        # one of: "A", "M", "R", "C", "D", "T"
    path: str          # new path (post-rename)
    old_path: str | None = None  # set only for R/C, source of the rename


def changed_files_since(project_dir: str, since_hash: str) -> list[FileChange] | None:
    """Return every file changed between `since_hash` and HEAD.

    Returns None when the delta cannot be computed:
    - not a git repository
    - `since_hash` is unknown (e.g. shallow clone, force-pushed history)
    - git itself fails

    An empty list means HEAD == since_hash (nothing changed). Callers
    should treat this as "use the cached report verbatim".
    """
    if not is_git_repo(project_dir):
        return None

    # Quick reachability check: is `since_hash` actually known to this repo?
    # `git cat-file -e` exits non-zero (returning None from run_git) when not.
    if run_git(project_dir, "cat-file", "-e", f"{since_hash}^{{commit}}") is None:
        log.info("git_delta: %s not reachable in repo, cannot compute delta", since_hash[:8])
        return None

    diff = run_git(
        project_dir,
        "diff",
        "--name-status",
        "-z",                   # NUL-separated; survives paths with spaces/quotes
        "--no-renames",         # treat rename as delete+add for simpler merging
        f"{since_hash}..HEAD",
    )
    if diff is None:
        return None
    if not diff:
        return []

    # `--name-status -z` separates *every* field with NUL (not tab), so the
    # stream is STATUS\0PATH\0STATUS\0PATH\0... — pair tokens up. With
    # --no-renames there are no R/C entries that would carry a third token.
    tokens = [t for t in diff.split("\0") if t]
    changes: list[FileChange] = []
    for i in range(0, len(tokens) - 1, 2):
        status = tokens[i][:1].upper()
        path = tokens[i + 1]
        if status in ("A", "M", "D", "T"):
            changes.append(FileChange(status=status, path=path))
    return changes


def find_ancestor_cache_hash(
    project_dir: str,
    *,
    max_lookback: int = 50,
) -> str | None:
    """Walk back from HEAD through first-parent ancestors looking for a
    commit that we have a cached scan for. Returns the matching hash, or
    None if HEAD itself is not in a git repo, or no ancestor up to
    `max_lookback` commits back has a cache entry.

    The lookback cap exists so we don't pay an O(history) cost on a fresh
    clone. 50 commits is generous for typical "scan once an hour" usage —
    if the user committed more than 50 times since the last scan, doing a
    full re-scan is the right call anyway.
    """
    if not is_git_repo(project_dir):
        return None
    cached = cache.list_cached_hashes(project_dir)
    if not cached:
        return None

    # Use `git rev-list --first-parent` so we walk linear history only —
    # avoiding chasing into merged feature branches we never scanned.
    rev_list = run_git(
        project_dir,
        "rev-list",
        "--first-parent",
        f"--max-count={max_lookback}",
        "HEAD",
    )
    if not rev_list:
        return None
    for line in rev_list.splitlines():
        h = line.strip()
        if h and h in cached:
            return h
    return None


@dataclass(frozen=True)
class DeltaPlan:
    """Summary of what a delta scan would do, given a current HEAD and the
    most recent cached ancestor. Pure data — orchestrator decides how to
    act on it (which scanners admit per-file delta, which must full-rerun)."""
    ancestor_hash: str
    changed: list[FileChange]

    @property
    def added_or_modified(self) -> list[str]:
        return [c.path for c in self.changed if c.status in ("A", "M", "T")]

    @property
    def deleted(self) -> list[str]:
        return [c.path for c in self.changed if c.status == "D"]


def plan_delta(project_dir: str) -> DeltaPlan | None:
    """Combine ancestor lookup and diff into a single plan.

    Returns None when no usable cache exists (or HEAD itself is already
    cached — caller should just use cache.get directly in that case).
    """
    ancestor = find_ancestor_cache_hash(project_dir)
    if ancestor is None:
        return None
    changed = changed_files_since(project_dir, ancestor)
    if changed is None:
        return None
    return DeltaPlan(ancestor_hash=ancestor, changed=changed)
