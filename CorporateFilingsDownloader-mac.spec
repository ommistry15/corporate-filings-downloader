# -*- mode: python ; coding: utf-8 -*-
# macOS build. Produces dist/Corporate Filings Downloader.app
# Build with:  ./build_release_mac.sh   (or: pyinstaller CorporateFilingsDownloader-mac.spec)
#
# Windows uses CorporateFilingsDownloader.spec (single-file .exe). On macOS a
# one-folder build wrapped in a .app BUNDLE is the supported layout: a
# single-file .app is deprecated by PyInstaller and starts slower.

APP_NAME = 'Corporate Filings Downloader'
VERSION = '1.1.0'

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/fonts', 'assets/fonts'), ('assets/icon.png', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Same reasoning as the Windows spec: lxml is optional at runtime.
    excludes=['lxml'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CorporateFilingsDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    # argv_emulation must stay off: the GUI re-invokes this same binary with
    # --cli-worker, and argv emulation would swallow those arguments.
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='CorporateFilingsDownloader',
)
app = BUNDLE(
    coll,
    name=APP_NAME + '.app',
    icon='assets/icon.icns',
    bundle_identifier='io.github.ommistry15.corporatefilingsdownloader',
    version=VERSION,
    info_plist={
        'CFBundleDisplayName': APP_NAME,
        'CFBundleShortVersionString': VERSION,
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
        'NSHumanReadableCopyright': 'MIT License',
    },
)
