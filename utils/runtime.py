"""源码运行和 Windows 分发包的路径约定。"""
import os
from pathlib import Path
import sys


def default_database():
    if getattr(sys, 'frozen', False):
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        return base / 'ScreenQualityAnalyzer' / 'analysis.sqlite3'
    return Path(__file__).resolve().parents[1] / 'data' / 'analysis.sqlite3'


def ffprobe_command():
    explicit = os.environ.get('SQA_FFPROBE')
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    if getattr(sys, 'frozen', False):
        bundled = Path(sys.executable).parent / 'tools' / 'ffprobe.exe'
        if bundled.is_file():
            return str(bundled)
    return 'ffprobe'
