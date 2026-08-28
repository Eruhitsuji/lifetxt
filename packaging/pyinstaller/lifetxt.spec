# PyInstaller spec for standalone lifetxt CLI binaries (#570).
#
# Bundles core + the `web` and `tui` optional extras into one complete
# artifact rather than shipping several partial bundles, per the issue's own
# "one complete artifact is preferable" option -- a user who downloads a
# standalone binary specifically because they do not want to manage Python
# packaging should not then have to pick which lifetxt they got.
#
# Build with (from the repository root, inside an environment that has
# lifetxt[web,tui] and pyinstaller installed):
#   pyinstaller packaging/pyinstaller/lifetxt.spec --distpath dist/standalone --clean --noconfirm
#
# See docs/en/distribution.md for the target matrix, verification steps, and
# known limitations of this bundling approach.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

REPO_ROOT = Path(SPECPATH).resolve().parents[1]

datas = []
datas += collect_data_files("lifetxt")
datas += collect_data_files("uvicorn")
if sys.platform == "win32":
    # No IANA timezone database ships with Windows; lifetxt's own runtime
    # dependency on tzdata (see pyproject.toml) is the same fix here.
    datas += collect_data_files("tzdata")

hidden_imports = []
hidden_imports += collect_submodules("uvicorn")
hidden_imports += collect_submodules("uvicorn.protocols")
hidden_imports += collect_submodules("uvicorn.lifespan")
hidden_imports += collect_submodules("uvicorn.loops")

a = Analysis(
    [str(REPO_ROOT / "packaging" / "pyinstaller" / "lifetxt_launcher.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="lifetxt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
