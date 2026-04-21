"""Tests for git survival checks."""

import subprocess

from core.health.models import HealthReport
from core.health.git_survival import (
    check_git_status, check_commit_quality, check_branch_awareness,
    check_gitignore, generate_cheat_sheet,
)


def _init_repo(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=str(tmp_path), capture_output=True,
    )


def test_git_status_not_repo(tmp_path):
    report = HealthReport(project_dir=str(tmp_path))
    check_git_status(report, str(tmp_path))
    assert any("Not a git" in f.title for f in report.findings)


def test_git_status_clean(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)

    report = HealthReport(project_dir=str(tmp_path))
    check_git_status(report, str(tmp_path))
    assert any("clean" in f.title.lower() for f in report.findings)


def test_git_status_dirty(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "b.py").write_text("y = 2\n")

    report = HealthReport(project_dir=str(tmp_path))
    check_git_status(report, str(tmp_path))
    status_findings = [f for f in report.findings if f.check_id == "git.status"]
    assert any("untracked" in f.message for f in status_findings)


def test_commit_quality_bad_message(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "fix"], cwd=str(tmp_path), capture_output=True)

    report = HealthReport(project_dir=str(tmp_path))
    check_commit_quality(report, str(tmp_path))
    commits = [f for f in report.findings if f.check_id == "git.commits"]
    assert any("Vague" in f.title for f in commits)


def test_branch_on_main(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)

    report = HealthReport(project_dir=str(tmp_path))
    check_branch_awareness(report, str(tmp_path))
    branches = [f for f in report.findings if f.check_id == "git.branches"]
    # Should warn about working on main/master
    assert len(branches) >= 1


def test_gitignore_missing(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n")

    report = HealthReport(project_dir=str(tmp_path))
    check_gitignore(report, str(tmp_path))
    gi = [f for f in report.findings if f.check_id == "git.gitignore"]
    assert any("No .gitignore" in f.title for f in gi)


def test_gitignore_exists_but_incomplete(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / ".gitignore").write_text("*.log\n")
    (tmp_path / ".env").write_text("SECRET=abc\n")

    report = HealthReport(project_dir=str(tmp_path))
    check_gitignore(report, str(tmp_path))
    gi = [f for f in report.findings if f.check_id == "git.gitignore"]
    assert any(".env" in f.message for f in gi)


def test_cheat_sheet_dirty(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")

    report = HealthReport(project_dir=str(tmp_path))
    generate_cheat_sheet(report, str(tmp_path))
    cheat = [f for f in report.findings if f.check_id == "git.cheatsheet"]
    assert len(cheat) == 1
    assert "git add" in cheat[0].message


def test_cheat_sheet_not_repo(tmp_path):
    report = HealthReport(project_dir=str(tmp_path))
    generate_cheat_sheet(report, str(tmp_path))
    cheat = [f for f in report.findings if f.check_id == "git.cheatsheet"]
    assert any("git init" in f.message for f in cheat)
