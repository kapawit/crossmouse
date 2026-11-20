# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPEC).parent.parent

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (
            str(root / "packaging" / "THIRD_PARTY_LICENSES.md"),
            "licenses",
        )
    ],
    hiddenimports=[
        "crossmouse.platform_win",
        "crossmouse.native_ui",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "crossmouse.clipboard",
        "crossmouse.engine",
        "crossmouse.link",
        "crossmouse.protocol",
        "crossmouse.crypto",
        "crossmouse.config",
        "crossmouse.debuglog",
        "cryptography",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["Xlib", "crossmouse.platform_linux", "tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CrossMouse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
