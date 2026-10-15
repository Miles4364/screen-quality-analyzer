"""离屏渲染真实 GUI 分析结果，便于无桌面环境做布局检查。"""
import argparse
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('video', nargs='?', default='samples/final_validation.mp4')
args = parser.parse_args()
app = QApplication([])
# 离屏平台不会自动发现 Windows 字体，显式加载仅用于渲染验收。
font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc'
if font.exists():
    font_id = QFontDatabase.addApplicationFont(str(font))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QFont(families[0], 10))
app.setStyle('Fusion')
window = MainWindow(args.video)
window.setStyleSheet(window.styleSheet().replace('Microsoft YaHei UI', 'Microsoft YaHei'))
window.show()
window.start_analysis()
exit_code = 1
stage = 'analysis'


def finish():
    global exit_code, stage
    if stage == 'analysis':
        if window.worker is not None:
            return
        if window.result is None or window.table.rowCount() != 4:
            print(window.status_label.text())
            timer.stop()
            window.close()
            return
        target = Path('docs/images/v03-analysis.png')
        target.parent.mkdir(parents=True, exist_ok=True)
        assert window.grab().save(str(target))
        print(window.result.statistics)
        window.table.selectRow(1)
        window.open_review()
        stage = 'review'
    elif stage == 'review':
        dialog = window.review_dialog
        if dialog.busy:
            return
        if dialog.current_frame is None:
            print(dialog.status.text())
        else:
            assert dialog.current_frame.index == round(25 * dialog.fps)
            assert dialog.grab().save('docs/images/v03-review.png')
            Path('screenshots').mkdir(exist_ok=True)
            dialog.save_image('screenshots/v03-freeze-25s.png')
            print(f'Frame {dialog.current_frame.index}, image {dialog.current_image.width()}x{dialog.current_image.height()}')
            exit_code = 0
        stage = 'closing'
        window.close()
    elif stage == 'closing' and window.review_dialog is None:
        timer.stop()
        app.quit()


timer = QTimer()
timer.timeout.connect(finish)
timer.start(100)
QTimer.singleShot(60000, window.close)
app.exec()
sys.exit(exit_code)
