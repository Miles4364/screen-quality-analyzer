"""启动桌面版：python gui_main.py [视频路径]。"""
import argparse
import sys
from utils.product import APP_NAME, APP_TITLE, VERSION


def main(argv=None):
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument('video_path', nargs='?', default='')
    parser.add_argument('--database', help='本地 SQLite 数据库路径')
    parser.add_argument('--auto-screenshot', action='store_true', help='运行样本并采集材料用真实窗口截图')
    parser.add_argument('--screenshot-dir', default='screenshots/v1', help='自动截图输出目录')
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
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setStyle('Fusion')
    if args.auto_screenshot:
        from tools.capture_materials import start_capture
        return start_capture(app, args.video_path, args.screenshot_dir)
    window = MainWindow(args.video_path, database_path=args.database)
    window.showMaximized()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
