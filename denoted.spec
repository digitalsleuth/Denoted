# -*- mode: python ; coding: utf-8 -*-

import re
from pathlib import Path

root = Path(SPECPATH)
__version__ = re.search(
    r'^__version__ = "([^"]+)"',
    (root / 'denoted' / '__init__.py').read_text(encoding='utf-8'),
    re.MULTILINE,
).group(1)
version_file = root / 'version.txt'
numbers = ', '.join(str(part) for part in ([int(part) for part in __version__.split('.')] + [0, 0, 0, 0])[:4])
version_text = version_file.read_text(encoding='utf-8')
for expected in (f'filevers=({numbers})', f'prodvers=({numbers})', f"'FileVersion', '{__version__}'", f"'ProductVersion', '{__version__}'", f"'Denoted v{__version__}.exe'"):
    if expected not in version_text:
        raise SystemExit(f'version.txt does not match denoted/__init__.py ({__version__}): missing {expected}')

a = Analysis(
    [str(root / 'denoted.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / 'denoted' / '_vendor' / 'qt_themes' / 'LICENSE'), 'denoted/_vendor/qt_themes'),
        (str(root / 'denoted' / 'assets' / 'denoted.png'), 'denoted/assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'numpy', 'pandas', 'matplotlib', 'scipy', 'PIL', 'IPython', 'pytest'],
    noarchive=False,
)
skipped = ('opengl32sw.dll', 'ucrtbase.dll')
a.binaries = [
    item
    for item in a.binaries
    if Path(item[0]).name.lower() not in skipped and not Path(item[0]).name.lower().startswith('api-ms-win-')
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'Denoted v{__version__}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(version_file),
    icon=str(root / 'denoted' / 'assets' / 'denoted.ico'),
)
