"""Security scanners — Python + Rust sentinel + system checks.

Public façade so existing imports (``from plugins.security_scan.scanners
import scan_X, Finding``) keep working after the split.

To add a new scanner: drop a file in this package and re-export
its public functions here.
"""
from plugins.security_scan.scanners.base import Finding, json_loads  # noqa: F401
from plugins.security_scan.scanners.deps import (  # noqa: F401
    scan_npm_audit,
    scan_pip_audit,
)
from plugins.security_scan.scanners.docker import scan_docker_security  # noqa: F401
from plugins.security_scan.scanners.git import scan_env_in_git  # noqa: F401
from plugins.security_scan.scanners.network import scan_exposed_ports  # noqa: F401
from plugins.security_scan.scanners.packages import (  # noqa: F401
    _is_typosquat,
    _KNOWN_MALICIOUS_NPM,
    _KNOWN_MALICIOUS_PYTHON,
    _POPULAR_NPM,
    _POPULAR_PYTHON,
    scan_suspicious_packages,
)
from plugins.security_scan.scanners.sentinel import (  # noqa: F401
    scan_container_escape,
    scan_env_leaks,
    scan_git_hooks,
    scan_sentinel_autostart,
    scan_sentinel_cron,
    scan_sentinel_filesystem,
    scan_sentinel_network,
    scan_sentinel_processes,
    scan_sentinel_secrets,
    scan_supply_chain,
)
from plugins.security_scan.scanners.system import (  # noqa: F401
    scan_firewall,
    scan_ssh_config,
    scan_sudoers,
    scan_system_updates,
    scan_world_writable,
)
