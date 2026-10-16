"""显式自检入口：在指定输出目录验证真正打包的 Qt/解码/数据库/报告。"""
import argparse
import json
import os
from pathlib import Path


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--video', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFontDatabase, QFont
    from PySide6.QtWidgets import QApplication
    from gui.main_window import MainWindow
    from gui.issue_review_dialog import IssueReviewDialog
    from openpyxl import load_workbook
    app = QApplication([])
    font = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'
    if font.exists():
        families = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(str(font)))
        if families:
            app.setFont(QFont(families[0],10))
    window = MainWindow(str(Path(args.video).resolve()), database_path=output/'smoke.sqlite3')
    window.show()
    state = {'stage': 'analysis', 'ok': False}
    window.start_analysis()

    def finish(error=None):
        timer.stop()
        if error:
            state['error'] = str(error)
        (output/'result.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        window.close()
        if window.worker is None:
            app.quit()

    def tick():
        try:
            if window.worker is not None:
                return
            if state['stage'] == 'analysis':
                if window.result is None or window.task_id is None:
                    raise RuntimeError(window.status_label.text())
                if not window.result.issues:
                    raise RuntimeError('自检视频至少需要一个异常以验证复核')
                original_score = window.result.quality.score
                dialog = IssueReviewDialog(window.store,window.task_id,0,{},window)
                dialog.status_picker.setCurrentIndex(1)
                dialog.note_edit.setPlainText('打包自检：确认异常')
                dialog.save()
                dialog.deleteLater()
                window.load_history(window.task_id)
                assert window.table.item(0,6).text() == '确认异常'
                assert window.result.quality.score == original_score
                state['statistics'] = window.result.statistics
                state['score'] = original_score
                state['stage'] = 'report'
                window.export_report_to(output/'report.xlsx',overwrite=True)
            elif state['stage'] == 'report':
                assert '报告已导出' in window.status_label.text(), window.status_label.text()
                book = load_workbook(output/'report.xlsx')
                assert book['异常明细']['K2'].value == '确认异常'
                book.close()
                assert window.grab().save(str(output/'window.png'))
                state.update(stage='complete',ok=True)
                finish()
        except Exception as exc:
            finish(exc)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    QTimer.singleShot(120000,lambda: finish('自检超时'))
    app.exec()
    return 0 if state['ok'] else 1
