# Build from the repository root with PyInstaller.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'launcher.py')], pathex=[str(root)],
             binaries=[], datas=[], hiddenimports=[],
             excludes=['pytest', 'tkinter', 'matplotlib'], noarchive=False)
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='ScreenQualityAnalyzer', console=False, upx=False)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='ScreenQualityAnalyzer-CLI', console=True, upx=False)
coll = COLLECT(gui, cli, a.binaries, a.datas, strip=False, upx=False,
               name='ScreenQualityAnalyzer')
