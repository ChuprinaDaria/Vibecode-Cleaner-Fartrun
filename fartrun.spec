# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Vibecode Cleaner Fartrun v3.0.0."""
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

# Rust compiled modules — paths depend on platform
if sys.platform == "win32":
    rust_ext = ".pyd"
elif sys.platform == "darwin":
    rust_ext = ".so"
else:
    rust_ext = ".so"

# Collect Rust binaries from site-packages (after maturin develop)
import importlib.util

rust_binaries = []
for mod_name in ("sentinel", "fartrun_health"):
    spec = importlib.util.find_spec(mod_name)
    if spec and spec.origin:
        rust_binaries.append((spec.origin, "."))

a = Analysis(
    [str(ROOT / "core" / "cli.py")],
    pathex=[str(ROOT)],
    binaries=rust_binaries,
    datas=[
        (str(ROOT / "sounds"), "sounds"),
        (str(ROOT / "i18n"), "i18n"),
        (str(ROOT / "data"), "data"),
        (str(ROOT / "config.toml.example"), "."),
        (str(ROOT / "tools.json"), "."),
    ],
    hiddenimports=[
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "core",
        "core.health",
        "core.mcp",
        "core.nagger",
        "core.platform_backends",
        "core.safety_net",
        "gui",
        "gui.pages",
        "gui.dialogs",
        "gui.widgets",
        "plugins",
        "plugins.security_scan",
        "plugins.docker_monitor",
        "plugins.port_map",
        "plugins.test_runner",
        "i18n",
        "i18n.en",
        "i18n.ua",
        "aiosqlite",
        "tomli_w",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy"],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="fartrun",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Fartrun.app",
        icon=None,
        bundle_identifier="pl.lazysoft.fartrun",
    )
