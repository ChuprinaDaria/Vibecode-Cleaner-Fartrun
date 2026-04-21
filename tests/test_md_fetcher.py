"""Tests for MD fetcher and parser."""

from core.md_fetcher import parse_resource_md, parse_education_md, Section, Resource


def test_parse_sections():
    md = """## MCP Servers
- [Playwright](https://github.com/anthropics/playwright-mcp) — Browser automation
- [PostgreSQL](https://github.com/example/pg-mcp) — Database queries

## Skills
- [Superpowers](https://github.com/example/superpowers) — TDD, debugging
"""
    sections = parse_resource_md(md)
    assert len(sections) == 2
    assert sections[0].title == "MCP Servers"
    assert len(sections[0].items) == 2
    assert sections[0].items[0].title == "Playwright"
    assert sections[0].items[0].url == "https://github.com/anthropics/playwright-mcp"
    assert sections[0].items[0].description == "Browser automation"
    assert sections[1].title == "Skills"
    assert len(sections[1].items) == 1


def test_parse_empty_md():
    sections = parse_resource_md("")
    assert sections == []


def test_parse_no_sections():
    md = "Just some text without sections"
    sections = parse_resource_md(md)
    assert sections == []


def test_parse_education_md():
    md = """## Docker Security
### en
- [Coursera: Docker Security](https://coursera.org/docker) — Container hardening
### ua
- [Prometheus: Docker](https://prometheus.org.ua/docker) — Kontainerna bezpeka
"""
    result = parse_education_md(md)
    assert "Docker Security" in result
    assert "en" in result["Docker Security"]
    assert "ua" in result["Docker Security"]
    assert result["Docker Security"]["en"][0].title == "Coursera: Docker Security"
    assert result["Docker Security"]["ua"][0].title == "Prometheus: Docker"


def test_parse_education_multiple_categories():
    md = """## Docker Security
### en
- [Course A](https://a.com) — Desc A

## Network Security
### en
- [Course B](https://b.com) — Desc B
### ua
- [Course C](https://c.com) — Desc C
"""
    result = parse_education_md(md)
    assert len(result) == 2
    assert len(result["Docker Security"]["en"]) == 1
    assert len(result["Network Security"]["en"]) == 1
    assert len(result["Network Security"]["ua"]) == 1
