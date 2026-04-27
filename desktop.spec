# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH)
datas = [(str(project_root / "staticfiles"), "staticfiles")]

for source_path, target_path in (
    (project_root / "cafeteria" / "templates", "cafeteria/templates"),
    (project_root / ".env", "."),
):
    if source_path.exists():
        datas.append((str(source_path), target_path))

binaries = []
hiddenimports = []

for package_name in ("cryptography", "django", "pymysql", "waitress", "webview", "whitenoise"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports


a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
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
    name="CaffPOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
