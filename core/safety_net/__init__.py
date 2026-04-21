"""Safety Net — public façade.

Re-exports preserve every name that lived in the original
``core/safety_net.py`` so external imports
(``from core.safety_net import SafetyNet, SavePointResult, ...``)
keep working unchanged.
"""
from core.safety_net.manager import SafetyNet  # noqa: F401
from core.safety_net.models import (  # noqa: F401
    PickResult,
    PickableFile,
    RollbackPreview,
    RollbackResult,
    SavePointResult,
    _SKIP_PATTERNS,
)
