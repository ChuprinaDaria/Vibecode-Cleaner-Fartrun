"""Tests for ScanContext + the _with_context scanner variants.

ScanContext is a per-run cache shared across scanners. These tests verify:
- Construction + cache stats API
- Calling a `_with_context` scanner produces the same result as the
  no-context full scan (equivalence)
- Re-using one ScanContext across module_map then dead_code produces
  cache hits on the tree cache (file is parsed once, walked twice)
"""

from __future__ import annotations

from pathlib import Path

import pytest

import health


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _make_small_project(root: Path) -> None:
    _write(root / "pkg" / "__init__.py", "")
    _write(root / "pkg" / "models.py",
           "class User:\n    pass\n\nclass Order:\n    pass\n")
    _write(root / "pkg" / "service.py",
           "from pkg.models import User\n\n"
           "def make_user():\n    return User()\n")
    _write(root / "pkg" / "unused.py",
           "import json\n"
           "def helper():\n    return 1\n")
    _write(root / "main.py",
           "from pkg.service import make_user\n"
           "if __name__ == '__main__':\n    print(make_user())\n")


# --- ScanContext API ---


class TestScanContextApi:
    def test_construct_empty(self):
        ctx = health.ScanContext()
        assert ctx.stats() == (0, 0, 0, 0)
        assert ctx.cache_size() == (0, 0)

    def test_stats_increase_after_module_map_run(self, tmp_path):
        _make_small_project(tmp_path)
        ctx = health.ScanContext()
        health.scan_module_map_with_context(ctx, str(tmp_path), [])
        files, _, trees, _ = (
            *ctx.stats()[:1], ctx.stats()[1], *ctx.stats()[2:3], ctx.stats()[3]
        )
        # At least one file read miss + one tree parse miss per source file.
        file_hits, file_misses, tree_hits, tree_misses = ctx.stats()
        assert file_misses >= 4         # 4 .py files (excluding __init__)
        assert tree_misses >= 4
        assert ctx.cache_size()[0] >= 4
        assert ctx.cache_size()[1] >= 4


# --- equivalence: with-context output matches without-context ---


class TestModuleMapEquivalence:
    def test_with_context_equals_no_context(self, tmp_path):
        _make_small_project(tmp_path)
        ctx = health.ScanContext()
        a = health.scan_module_map(str(tmp_path), [])
        b = health.scan_module_map_with_context(ctx, str(tmp_path), [])

        assert sorted(p for p, _ in a.hub_modules) == \
               sorted(p for p, _ in b.hub_modules)
        assert sorted((cd.file_a, cd.file_b) for cd in a.circular_deps) == \
               sorted((cd.file_a, cd.file_b) for cd in b.circular_deps)
        assert sorted(a.orphan_candidates) == sorted(b.orphan_candidates)


class TestDeadCodeEquivalence:
    def test_with_context_equals_no_context(self, tmp_path):
        _make_small_project(tmp_path)
        ctx = health.ScanContext()
        a = health.scan_dead_code(str(tmp_path), [])
        b = health.scan_dead_code_with_context(ctx, str(tmp_path), [])

        assert sorted((u.path, u.line, u.name) for u in a.unused_imports) == \
               sorted((u.path, u.line, u.name) for u in b.unused_imports)
        assert sorted((d.path, d.line, d.name, d.kind)
                      for d in a.unused_definitions) == \
               sorted((d.path, d.line, d.name, d.kind)
                      for d in b.unused_definitions)
        assert sorted(a.orphan_files) == sorted(b.orphan_files)


# --- the actual cache-sharing win between scanners ---


class TestCacheSharingAcrossScanners:
    def test_dead_code_after_module_map_reuses_trees(self, tmp_path):
        """Run module_map first to populate the tree cache, then dead_code.
        The second scan must produce tree-cache HITS for every file
        module_map saw — that's the whole point of ScanContext."""
        _make_small_project(tmp_path)
        ctx = health.ScanContext()

        # First scan: populates cache (all misses).
        health.scan_module_map_with_context(ctx, str(tmp_path), [])
        _, _, _, tree_misses_after_first = ctx.stats()
        assert tree_misses_after_first >= 4
        cached_count = ctx.cache_size()[1]

        # Second scan: must reuse those trees rather than re-parsing.
        health.scan_dead_code_with_context(ctx, str(tmp_path), [])
        _, _, tree_hits_after_second, tree_misses_after_second = ctx.stats()

        # dead_code visits the same files module_map did, so each parse
        # call should resolve to a cache hit. tree_misses must NOT have
        # grown by the file count again.
        new_misses = tree_misses_after_second - tree_misses_after_first
        # dead_code may visit a few files module_map skipped (or vice
        # versa) so allow a small slack — what we really care about is
        # that we got a meaningful number of hits.
        assert tree_hits_after_second >= cached_count - new_misses
        assert tree_hits_after_second >= 4

    def test_file_cache_shared_too(self, tmp_path):
        """Same idea for file contents — module_map reads each file once;
        dead_code reading the same files must hit the file cache."""
        _make_small_project(tmp_path)
        ctx = health.ScanContext()
        health.scan_module_map_with_context(ctx, str(tmp_path), [])
        file_misses_after_first = ctx.stats()[1]

        health.scan_dead_code_with_context(ctx, str(tmp_path), [])
        file_hits_total = ctx.stats()[0]
        file_misses_after_second = ctx.stats()[1]

        # New file-cache misses on the second scan should be small (only
        # for files dead_code visits but module_map didn't, which for our
        # fixture is zero or one).
        new_misses = file_misses_after_second - file_misses_after_first
        assert new_misses <= 1
        assert file_hits_total >= 4

    def test_monsters_after_module_map_reuses_cache(self, tmp_path):
        """monsters scans files >500 lines. After module_map populates
        the cache for those files, scan_monsters_with_context must not
        record new tree-cache misses for them."""
        _write(tmp_path / "big.py",
               "\n".join(f"x{i} = {i}" for i in range(700)) + "\n")
        _write(tmp_path / "tiny.py", "x = 1\n")
        ctx = health.ScanContext()
        health.scan_module_map_with_context(ctx, str(tmp_path), [])
        tree_misses_before = ctx.stats()[3]
        result = health.scan_monsters_with_context(ctx, str(tmp_path))
        tree_misses_after = ctx.stats()[3]
        # big.py was already parsed by module_map → no new miss for it.
        assert tree_misses_after == tree_misses_before
        assert any(m.path == "big.py" for m in result.monsters)

    def test_tech_debt_after_module_map_reuses_cache(self, tmp_path):
        _make_small_project(tmp_path)
        ctx = health.ScanContext()
        health.scan_module_map_with_context(ctx, str(tmp_path), [])
        tree_misses_before = ctx.stats()[3]
        tree_size_before = ctx.cache_size()[1]

        health.scan_tech_debt_with_context(ctx, str(tmp_path))

        tree_misses_after = ctx.stats()[3]
        tree_hits_after = ctx.stats()[2]
        # tech_debt parses Python files for missing_types AND error_gaps —
        # both can resolve to the same cached tree, so we expect hits.
        assert tree_hits_after >= 1
        # Cache size shouldn't balloon — every Python file the scanner
        # visits should already be in there.
        new_entries = ctx.cache_size()[1] - tree_size_before
        assert new_entries == 0

    def test_overengineering_after_module_map_reuses_cache(self, tmp_path):
        _make_small_project(tmp_path)
        ctx = health.ScanContext()
        health.scan_module_map_with_context(ctx, str(tmp_path), [])
        tree_size_before = ctx.cache_size()[1]
        tree_hits_before = ctx.stats()[2]

        health.scan_overengineering_with_context(ctx, str(tmp_path))

        tree_hits_after = ctx.stats()[2]
        # Python single_method_classes parse on each .py file should hit
        # the cache populated by module_map.
        assert tree_hits_after >= tree_hits_before + 1
        new_entries = ctx.cache_size()[1] - tree_size_before
        # overengineering only handles Python here, so no new TS/JS trees.
        assert new_entries == 0


# --- equivalence: with-context output matches without-context for new scanners ---


class TestExtendedEquivalence:
    def test_monsters_equivalence(self, tmp_path):
        _write(tmp_path / "big.py",
               "\n".join(f"x{i} = {i}" for i in range(700)) + "\n")
        _write(tmp_path / "klass.py",
               "class A:\n    def f(self):\n        return 1\n" * 200)
        a = health.scan_monsters(str(tmp_path))
        b = health.scan_monsters_with_context(health.ScanContext(), str(tmp_path))
        assert sorted(m.path for m in a.monsters) == sorted(m.path for m in b.monsters)
        assert sorted((m.path, m.lines, m.functions, m.classes) for m in a.monsters) == \
               sorted((m.path, m.lines, m.functions, m.classes) for m in b.monsters)

    def test_tech_debt_equivalence(self, tmp_path):
        _write(tmp_path / "x.py",
               "# TODO: fix\n"
               "def f(a, b):\n    try:\n        pass\n    except:\n        pass\n")
        a = health.scan_tech_debt(str(tmp_path))
        b = health.scan_tech_debt_with_context(health.ScanContext(), str(tmp_path))
        assert sorted((t.path, t.line, t.kind) for t in a.todos) == \
               sorted((t.path, t.line, t.kind) for t in b.todos)
        assert sorted((m.path, m.line, m.function_name) for m in a.missing_types) == \
               sorted((m.path, m.line, m.function_name) for m in b.missing_types)
        assert sorted((e.path, e.line, e.kind) for e in a.error_gaps) == \
               sorted((e.path, e.line, e.kind) for e in b.error_gaps)

    def test_overengineering_equivalence(self, tmp_path):
        # A class with a single method is the canonical overengineering trigger.
        _write(tmp_path / "service.py",
               "class Service:\n    def run(self):\n        return 1\n")
        a = health.scan_overengineering(str(tmp_path))
        b = health.scan_overengineering_with_context(
            health.ScanContext(), str(tmp_path),
        )
        assert sorted((i.path, i.kind) for i in a.issues) == \
               sorted((i.path, i.kind) for i in b.issues)
