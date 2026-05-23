# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the local Z88 topology optimizer wrapper."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path.cwd()

datas = [
    (str(ROOT / "web"), "web"),
    (str(ROOT / "presets"), "presets"),
    (str(ROOT / "Z88_INTEGRATION.md"), "."),
    (str(ROOT / "z88_integration_plan.md"), "."),
    (str(ROOT / "FILE_FORMAT_REFERENCE.md"), "."),
]
if (ROOT / "samples").is_dir():
    datas.append((str(ROOT / "samples"), "samples"))

hiddenimports = []
for package in ("uvicorn", "fastapi", "starlette", "pydantic", "trimesh", "scipy", "skimage"):
    hiddenimports.extend(collect_submodules(package))

a = Analysis(
    [str(ROOT / "packaging" / "z88_topopt_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Z88TopologyOptimizer",
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
