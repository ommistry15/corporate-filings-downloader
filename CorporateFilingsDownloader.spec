# -*- mode: python ; coding: utf-8 -*-
# Build with:  pyinstaller CorporateFilingsDownloader.spec
# (or just run build_release.ps1, which does this and packages the zip)


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/fonts', 'assets/fonts'), ('assets/icon.ico', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # lxml is optional at runtime (research_downloader falls back to
    # html.parser); excluding it avoids PyInstaller missing bs4's
    # runtime-dispatched lxml imports.
    excludes=['lxml'],
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
    name='CorporateFilingsDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX-compressed executables trip antivirus heuristics far more often.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    # No modal "Unhandled exception" dialog: a crash should never leave a
    # blocked, invisible window behind (errors go to the log box instead).
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
    version='version_info.txt',
)
