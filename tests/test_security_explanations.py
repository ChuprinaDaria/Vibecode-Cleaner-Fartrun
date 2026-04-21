"""Tests for security finding explanations."""

from gui.security_explanations import get_explanation, get_human_description, _EXPLANATIONS_EN as EXPLANATIONS


def test_privileged_container_explanation():
    explanation = get_explanation("docker", "runs in privileged mode")
    assert explanation is not None
    assert "what" in explanation
    assert "risk" in explanation
    assert "fix" in explanation
    assert len(explanation["what"]) > 10


def test_docker_sock_explanation():
    assert get_explanation("docker", "docker.sock mounted inside container") is not None


def test_root_user_explanation():
    assert get_explanation("docker", "runs as root") is not None


def test_env_in_git_explanation():
    assert get_explanation("config", ".env file committed in git") is not None


def test_exposed_port_explanation():
    assert get_explanation("network", "exposed on 0.0.0.0") is not None


def test_broad_permissions_explanation():
    assert get_explanation("config", "Broad permissions") is not None


def test_latest_tag_explanation():
    assert get_explanation("docker", ":latest tag") is not None


def test_host_network_explanation():
    assert get_explanation("docker", "host network mode") is not None


def test_unknown_finding_returns_generic():
    explanation = get_explanation("unknown", "something weird happened")
    assert explanation is not None
    assert "what" in explanation


def test_all_explanations_have_required_keys():
    for key, exp in EXPLANATIONS.items():
        assert "what" in exp, f"Missing 'what' in {key}"
        assert "risk" in exp, f"Missing 'risk' in {key}"
        assert "fix" in exp, f"Missing 'fix' in {key}"


def test_human_description_privileged():
    desc = get_human_description("docker", "nginx: runs in privileged mode")
    # May return EN or UA text depending on language setting
    assert "admin" in desc.lower() or "attacker" in desc.lower() or "адмін" in desc.lower()


def test_human_description_root():
    desc = get_human_description("docker", "nginx: runs as root (no USER set)")
    assert desc != "nginx: runs as root (no USER set)"


def test_human_description_passthrough():
    desc = get_human_description("unknown", "some unknown thing")
    assert desc == "some unknown thing"
