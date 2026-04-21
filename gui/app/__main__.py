"""``python -m gui.app`` entrypoint."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable when running ``python -m gui.app``
# from outside the project directory.
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from gui.app.main import main

if __name__ == "__main__":
    main()
