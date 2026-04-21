"""Re-export framework detection for symmetry with docker_monitor/port_map."""
from core.health.test_detector import detect_framework

__all__ = ["detect_framework"]
