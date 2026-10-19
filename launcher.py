"""分发包的 GUI、CLI 和显式自检入口。"""
from pathlib import Path
import sys


def main():
    if '--self-test' in sys.argv[1:]:
        from tools.packaged_smoke import main as smoke
        return smoke(sys.argv[1:])
    if Path(sys.executable).stem.endswith('-CLI') or '--cli' in sys.argv[1:]:
        from main import main as cli
        return cli([arg for arg in sys.argv[1:] if arg != '--cli'])
    from gui_main import main as gui
    return gui()


if __name__ == '__main__':
    sys.exit(main())
