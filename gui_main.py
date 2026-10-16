"""启动桌面版：python gui_main.py [视频路径]。"""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description='投屏质量分析桌面版 V0.9.1')
    parser.add_argument('video_path', nargs='?', default='')
    parser.add_argument('--database', help='本地 SQLite 数据库路径')
    args = parser.parse_args(argv)
    try:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        if exc.name != 'PySide6':
            raise
        print('请先安装桌面依赖：python -m pip install -r requirements-gui.txt', file=sys.stderr)
        return 1
    app = QApplication(sys.argv[:1])
    app.setApplicationName('投屏质量分析')
    app.setStyle('Fusion')
    window = MainWindow(args.video_path, database_path=args.database)
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
