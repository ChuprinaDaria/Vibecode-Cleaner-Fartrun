"""Tests for file_explainer — pattern → human explanation mapping."""

from core.file_explainer import explain_file


def test_docker_compose():
    assert "Docker" in explain_file("docker-compose.yml")


def test_dockerfile():
    assert "Docker" in explain_file("Dockerfile")
    assert "Docker" in explain_file("backend/Dockerfile")


def test_requirements():
    assert "Python" in explain_file("requirements.txt")
    assert "dependenc" in explain_file("requirements.txt").lower()


def test_package_json():
    result = explain_file("package.json")
    assert "Node" in result or "JS" in result


def test_env_file():
    result = explain_file(".env")
    assert "variable" in result.lower() or "secret" in result.lower() or "config" in result.lower()


def test_migration():
    result = explain_file("apps/users/migrations/0002_add_email.py")
    assert "migration" in result.lower() or "database" in result.lower()


def test_python_file():
    result = explain_file("src/worker.py")
    assert result  # not empty, generic explanation


def test_unknown_file():
    result = explain_file("something.xyz")
    assert result  # still returns something, not empty


def test_gitignore():
    result = explain_file(".gitignore")
    assert "git" in result.lower() or "ignore" in result.lower()


def test_makefile():
    result = explain_file("Makefile")
    assert result


def test_github_actions():
    result = explain_file(".github/workflows/ci.yml")
    assert "CI" in result or "pipeline" in result.lower() or "action" in result.lower()


def test_alembic_migration():
    result = explain_file("alembic/versions/abc123_add_users.py")
    assert "migration" in result.lower() or "database" in result.lower()


def test_pyproject_toml():
    result = explain_file("pyproject.toml")
    assert "Python" in result or "project" in result.lower()


def test_lock_files():
    result = explain_file("package-lock.json")
    assert "lock" in result.lower() or "dependenc" in result.lower()
    result2 = explain_file("poetry.lock")
    assert "lock" in result2.lower() or "dependenc" in result2.lower()
