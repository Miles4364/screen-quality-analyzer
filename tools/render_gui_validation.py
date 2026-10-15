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

def finish():
    global exit_code
    if window.worker is not None:
        return
    if window.result is not None and window.table.rowCount() == 4:
        target = Path('docs/images/v02-analysis.png')
        target.parent.mkdir(parents=True, exist_ok=True)
        assert window.grab().save(str(target))
        print(window.result.statistics)
        exit_code = 0
    else:
        print(window.status_label.text())
    timer.stop()
    window.close()
    app.quit()

timer = QTimer()
timer.timeout.connect(finish)
timer.start(100)
QTimer.singleShot(60000, window.close)
app.exec()
sys.exit(exit_code)
