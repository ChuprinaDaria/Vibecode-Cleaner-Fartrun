"""Tests for project detector."""
from pathlib import Path
from core.project_detector import detect_projects, get_last_project, save_last_project
from core.history import HistoryDB


def test_detect_projects_no_claude_dir():
    projects = detect_projects("/nonexistent/path")
    assert projects == []


def test_detect_projects_from_claude_dir(tmp_path):
    # Create a fake project dir that maps to a real tmp_path subdir
    real_project = tmp_path / "myproject"
    real_project.mkdir()

    # Encode the path as Claude would: /tmp/xxx/myproject -> -tmp-xxx-myproject
    encoded = "-" + str(real_project).lstrip("/").replace("/", "-")

    proj_dir = tmp_path / ".claude" / "projects"
    proj_dir.mkdir(parents=True)
    fake_proj = proj_dir / encoded
    fake_proj.mkdir()
    (fake_proj / "session.jsonl").write_text("{}")

    projects = detect_projects(str(tmp_path / ".claude"))
    assert len(projects) >= 1
    assert projects[0]["path"] == str(real_project)


def test_save_and_get_last_project():
    db = HistoryDB(db_path=":memory:")
    db.init()
    assert get_last_project(db) is None
    save_last_project(db, "/home/user/proj")
    assert get_last_project(db) == "/home/user/proj"
    save_last_project(db, "/home/user/proj2")
    assert get_last_project(db) == "/home/user/proj2"
