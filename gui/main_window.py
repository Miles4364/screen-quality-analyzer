"""选择文件、后台分析、取消和结果展示。"""
from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QComboBox, QInputDialog,
)
from gui.worker import AnalysisWorker
from storage.analysis_store import AnalysisStore, StorageError
from utils.time_util import seconds_to_time


class MainWindow(QMainWindow):
    def __init__(self, video_path='', database_path=None):
        super().__init__()
        self.store = AnalysisStore(database_path) if database_path is not None else AnalysisStore()
        self.task_id = None
        self.pending_title = None
        self.pending_project = None
        self.pending_project_name = None
        self.worker = None
        self.result = None
        self.review_dialog = None
        self.report_active = False
        self._cancel_requested = False
        self._close_pending = False
        self.setWindowTitle('智能会议设备投屏质量分析系统 · V0.6')
        self.resize(1050, 800)
        self.setMinimumSize(800, 580)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)
        title = QLabel('投屏质量分析')
        title.setObjectName('title')
        layout.addWidget(title)
        subtitle = QLabel('导入录制视频，定位黑屏与疑似冻结片段。')
        subtitle.setObjectName('muted')
        layout.addWidget(subtitle)
        row = QHBoxLayout()
        self.path_edit = QLineEdit(video_path)
        self.path_edit.setAccessibleName('视频路径')
        self.path_edit.setPlaceholderText('选择视频，或在此粘贴本地文件路径')
        self.browse_button = QPushButton('选择视频')
        self.browse_button.clicked.connect(self.choose_file)
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.browse_button)
        layout.addLayout(row)
        task_row = QHBoxLayout()
        self.project_picker = QComboBox()
        self.project_picker.addItem('未分组', None)
        self.new_project_button = QPushButton('新建项目')
        self.new_project_button.clicked.connect(self.create_project)
        self.task_title_edit = QLineEdit()
        self.task_title_edit.setMaxLength(120)
        self.task_title_edit.setPlaceholderText('任务名称（留空使用视频文件名）')
        task_row.addWidget(QLabel('项目'))
        task_row.addWidget(self.project_picker)
        task_row.addWidget(self.new_project_button)
        task_row.addWidget(self.task_title_edit, 1)
        layout.addLayout(task_row)
        self.metadata_label = QLabel('视频参数将在开始分析后显示')
        self.metadata_label.setTextFormat(Qt.TextFormat.PlainText)
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setObjectName('card')
        layout.addWidget(self.metadata_label)
        controls = QHBoxLayout()
        self.start_button = QPushButton('开始分析')
        self.start_button.setObjectName('primary')
        self.start_button.clicked.connect(self.start_analysis)
        self.cancel_button = QPushButton('取消分析')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_analysis)
        controls.addWidget(self.start_button)
        controls.addWidget(self.cancel_button)
        self.history_button = QPushButton('历史记录')
        self.history_button.clicked.connect(self.open_history)
        self.save_result_button = QPushButton('保存结果')
        self.save_result_button.setEnabled(False)
        self.save_result_button.clicked.connect(self.save_result)
        controls.addWidget(self.history_button)
        controls.addWidget(self.save_result_button)
        controls.addStretch()
        self.status_label = QLabel('就绪')
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        controls.addWidget(self.status_label, 1)
        layout.addLayout(controls)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.summary_label = QLabel('尚无分析结果')
        self.summary_label.setObjectName('summary')
        layout.addWidget(self.summary_label)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['异常类型', '开始时间', '结束时间', '持续时间', '等级', '说明'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.open_review)
        layout.addWidget(self.table, 1)
        self.review_button = QPushButton('查看截图 / 跳转视频')
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.open_review)
        review_row = QHBoxLayout()
        review_row.addWidget(self.review_button)
        self.screenshots_button = QPushButton('已保存截图')
        self.screenshots_button.setEnabled(False)
        self.screenshots_button.clicked.connect(self.open_screenshots)
        review_row.addWidget(self.screenshots_button)
        self.export_button = QPushButton('导出 Excel 报告')
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_dialog)
        review_row.addWidget(self.export_button)
        layout.addLayout(review_row)
        hint = QLabel('判定提示：静态 PPT 或低运动画面可能触发疑似冻结，请结合视频人工复核。')
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.path_edit.textChanged.connect(self._path_changed)
        self.setStyleSheet('''
            QMainWindow { background: #f4f7fb; }
            QWidget { color: #24344a; font-family: "Microsoft YaHei UI"; font-size: 14px; }
            QLabel#title { font-size: 28px; font-weight: 700; }
            QLabel#muted { color: #65758b; }
            QLabel#card { background: white; border: 1px solid #dbe3ee; border-radius: 8px; padding: 18px; }
            QLabel#summary { font-size: 16px; font-weight: 600; }
            QLineEdit { background: white; border: 1px solid #cbd6e4; border-radius: 6px; padding: 10px; }
            QPushButton { background: white; border: 1px solid #cbd6e4; border-radius: 6px; padding: 10px 20px; }
            QPushButton:hover { background: #e8eff9; }
            QPushButton#primary { background: #245fcc; color: white; border: none; }
            QPushButton:disabled { background: #e6ebf2; color: #8995a6; }
            QProgressBar { border: none; background: #e0e7f1; border-radius: 5px; text-align: center; height: 20px; }
            QProgressBar::chunk { background: #4585e5; border-radius: 5px; }
            QTableWidget { background: white; alternate-background-color: #f6f9fd; gridline-color: #e5ebf3; border: 1px solid #dbe3ee; }
            QHeaderView::section { background: #eaf0f8; padding: 10px; border: none; font-weight: 600; }
        ''')
        self.refresh_projects()

    @Slot()
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择待分析视频', '',
            '视频文件 (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.ts);;所有文件 (*)',
        )
        if path:
            self.path_edit.setText(path)

    @Slot()
    def _path_changed(self):
        if self.worker is None:
            self.result = None
            self.export_button.setEnabled(False)
            self.task_id = None
            self.task_title_edit.clear()
            self.save_result_button.setEnabled(False)
            self.screenshots_button.setEnabled(False)
            self.review_button.setEnabled(False)
            self.table.setRowCount(0)
            self.summary_label.setText('尚无分析结果')
            self.metadata_label.setText('视频参数将在开始分析后显示')
            self.status_label.setText('就绪')
            self.progress_bar.setValue(0)

    @Slot()
    def start_analysis(self):
        if self.worker is not None:
            return
        path = self.path_edit.text().strip()
        if not Path(path).is_file():
            self.status_label.setText('请选择有效的视频文件')
            return
        self.result = None
        self.export_button.setEnabled(False)
        self.task_id = None
        self.save_result_button.setEnabled(False)
        self.screenshots_button.setEnabled(False)
        self.review_button.setEnabled(False)
        self.pending_title = self.task_title_edit.text().strip() or None
        self.pending_project = self.project_picker.currentData()
        self.pending_project_name = self.project_picker.currentText() if self.pending_project else None
        self._cancel_requested = False
        self.table.setRowCount(0)
        self.summary_label.setText('正在分析，完成后显示结果')
        self.metadata_label.setText('正在读取视频参数…')
        self.status_label.setText('正在解析视频…')
        self.progress_bar.setRange(0, 0)
        self._set_busy(True)
        self.worker = AnalysisWorker(path, parent=self)
        self.worker.metadata_ready.connect(self._show_metadata)
        self.worker.progress.connect(self._show_progress)
        self.worker.result_ready.connect(self._show_result)
        self.worker.cancelled.connect(self._show_cancelled)
        self.worker.failed.connect(self._show_error)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _set_busy(self, busy):
        self.project_picker.setEnabled(not busy)
        self.new_project_button.setEnabled(not busy)
        self.task_title_edit.setEnabled(not busy)
        self.export_button.setEnabled(not busy and self.result is not None)
        self.save_result_button.setEnabled(not busy and self.result is not None and self.task_id is None)
        self.history_button.setEnabled(not busy)
        self.start_button.setEnabled(not busy)
        self.browse_button.setEnabled(not busy)
        self.path_edit.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    @Slot()
    def cancel_analysis(self):
        if self.worker is not None:
            self._cancel_requested = True
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText('正在取消，等待当前操作完成…')

    @Slot(object)
    def _show_metadata(self, metadata):
        self.metadata_label.setText(
            f'{metadata.filename}\n{metadata.resolution}  ·  {metadata.fps:.3f} FPS  ·  '
            f'{seconds_to_time(metadata.duration)}  ·  {metadata.codec}'
        )

    @Slot(int, int)
    def _show_progress(self, processed, total):
        if self._cancel_requested:
            return
        if total > 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(min(99, int(processed * 100 / total)))
            self.status_label.setText(f'正在分析：{processed} / {total} 帧')
        else:
            self.progress_bar.setRange(0, 0)
            self.status_label.setText(f'正在分析：已读取 {processed} 帧')

    @Slot(object)
    def _show_result(self, result, persist=True):
        # 取消与结果信号可能同时入队；用户发出取消后不展示成功结果。
        if self._cancel_requested:
            self._show_cancelled()
            return
        self.result = result
        self.export_button.setEnabled(self.worker is None)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        stats = result.statistics
        self.summary_label.setText(f'黑屏 {stats["black_count"]} 段    疑似冻结 {stats["freeze_count"]} 段    共 {stats["total_count"]} 个异常')
        self.status_label.setText(f'分析完成 · {result.processed_frames} 帧 · {result.processing_time:.2f} 秒')
        self.review_button.setEnabled(bool(result.issues))
        self.table.setRowCount(len(result.issues))
        for row, issue in enumerate(result.issues):
            values = [
                '黑屏' if issue.issue_type == 'BLACK_SCREEN' else '疑似冻结',
                seconds_to_time(issue.start_time), seconds_to_time(issue.end_time),
                f'{issue.duration:.3f} 秒', {'LOW': '低', 'MEDIUM': '中', 'HIGH': '高'}[issue.severity],
                issue.description,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)

        if persist:
            self.save_result()

    def save_result(self):
        if self.result is None or self.task_id is not None:
            return
        try:
            self.task_id = self.store.save_result(self.result, title=self.pending_title, project_id=self.pending_project)
            self.save_result_button.setEnabled(False)
            self.screenshots_button.setEnabled(True)
            self.status_label.setText(self.status_label.text() + ' · 已保存')
        except StorageError as exc:
            self.save_result_button.setEnabled(True)
            self.status_label.setText(f'结果未保存，可点击“保存结果”重试：{exc}')

    def refresh_projects(self, selected='keep'):
        if selected == 'keep':
            selected = self.project_picker.currentData()
        try:
            projects = self.store.list_projects()
            self.project_picker.clear()
            self.project_picker.addItem('未分组', None)
            for project in projects:
                self.project_picker.addItem(project['name'], project['id'])
            index = self.project_picker.findData(selected)
            self.project_picker.setCurrentIndex(max(0, index))
        except StorageError as exc:
            self.status_label.setText(f'项目列表不可用：{exc}')

    def create_project(self):
        name, accepted = QInputDialog.getText(self, '新建项目', '项目名称（最多 80 字符）')
        if accepted:
            try:
                self.refresh_projects(self.store.create_project(name))
            except StorageError as exc:
                self.status_label.setText(str(exc))

    def open_history(self):
        if self.worker is not None:
            return
        from gui.history_dialog import HistoryDialog
        dialog = HistoryDialog(self.store, self)
        if dialog.exec() and dialog.selected_task_id:
            self.load_history(dialog.selected_task_id)
        dialog.deleteLater()
        self.refresh_projects()

    def load_history(self, task_id):
        if self.worker is not None or self.review_dialog is not None:
            return
        try:
            task = self.store.load_task(task_id)
        except StorageError as exc:
            self.status_label.setText(str(exc))
            return
        self.path_edit.setText(task['result'].video_metadata.filepath)
        self._cancel_requested = False
        self.task_id = task_id
        self.refresh_projects(task['project_id'])
        self.task_title_edit.setText(task['title'])
        self._show_metadata(task['result'].video_metadata)
        self._show_result(task['result'], persist=False)
        self.save_result_button.setEnabled(False)
        self.screenshots_button.setEnabled(True)
        available = self.store.source_available(task)
        self.review_button.setEnabled(available and bool(self.result.issues))
        self.status_label.setText('已打开历史结果' if available else '历史结果已打开；源视频缺失或已更改，无法复核。已有截图仍可查看。')

    def export_dialog(self):
        if self.result is None or self.worker is not None:
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出 Excel 报告', '投屏质量分析报告.xlsx', 'Excel 工作簿 (*.xlsx)')
        if path:
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
                # 补扩展名后若存在目标，让对话框对最终文件名再次确认覆盖。
                if Path(path).exists():
                    from PySide6.QtWidgets import QMessageBox
                    if QMessageBox.question(self, '覆盖报告', f'文件已存在，是否覆盖？\n{path}') != QMessageBox.StandardButton.Yes:
                        return
            self.export_report_to(path, overwrite=True)

    def export_report_to(self, path, overwrite=False):
        if self.result is None or self.worker is not None:
            return
        from copy import deepcopy
        from gui.report_worker import ReportWorker
        try:
            task = self.store.load_task(self.task_id) if self.task_id else None
        except StorageError as exc:
            self.status_label.setText(f'无法读取报告资料：{exc}')
            return
        if task is None:
            task = {'title': self.pending_title or self.result.video_metadata.filename,
                    'project_name': self.pending_project_name}
        self.worker = ReportWorker(deepcopy(self.result), path,
                                   {'task': deepcopy(task), 'overwrite': overwrite,
                                    'protected_paths': [self.store.path]}, self)
        self.report_active = True
        self._cancel_requested = False
        self._set_busy(True)
        self.cancel_button.setText('取消导出')
        self.progress_bar.setRange(0, 0)
        self.status_label.setText('正在生成 Excel 报告…')
        self.worker.ready.connect(self._report_ready)
        self.worker.failed.connect(self._report_failed)
        self.worker.cancelled.connect(self._report_cancelled)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    @Slot(str)
    def _report_ready(self, path):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText(f'报告已导出：{path}')

    @Slot(str)
    def _report_failed(self, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText(f'报告导出失败（分析结果保留）：{message}')

    @Slot()
    def _report_cancelled(self):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText('报告导出已取消，分析结果保留')

    def open_screenshots(self):
        if self.task_id is None or self.worker is not None:
            return
        from gui.history_dialog import ScreenshotsDialog
        try:
            records = self.store.list_screenshots(self.task_id)
        except StorageError as exc:
            self.status_label.setText(str(exc))
            return
        dialog = ScreenshotsDialog(records, self)
        dialog.exec()
        dialog.deleteLater()

    @Slot()
    def _show_cancelled(self):
        self.result = None
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText('已取消')
        self.summary_label.setText('分析已取消，未生成结果')

    @Slot(str)
    def _show_error(self, message):
        if self._cancel_requested:
            self._show_cancelled()
            return
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText('分析失败，请检查文件及 FFprobe 安装')
        self.summary_label.setText('未生成结果')
        self.metadata_label.setText(message)

    @Slot()
    def _finished(self):
        worker = self.worker
        self.worker = None
        self.report_active = False
        self.cancel_button.setText('取消分析')
        self._set_busy(False)
        if worker is not None:
            worker.deleteLater()
        if self._close_pending:
            self.close()

    def open_review(self, *args):
        if self.result is None or not self.result.issues or self.worker is not None:
            return
        if self.review_dialog is not None:
            self.review_dialog.raise_()
            return
        if self.task_id is not None:
            try:
                if not self.store.source_available(self.store.load_task(self.task_id)):
                    self.status_label.setText('源视频缺失或已更改，无法复核；已有截图仍可查看。')
                    return
            except StorageError as exc:
                self.status_label.setText(str(exc))
                return
        from gui.review_dialog import ReviewDialog
        row = self.table.currentRow()
        if row < 0:
            row = 0
        self.table.selectRow(row)
        self.review_dialog = ReviewDialog(self.result, self.result.issues[row], self,
                                          store=self.store if self.task_id else None,
                                          task_id=self.task_id, issue_ordinal=row)
        self.review_dialog.setModal(True)
        self.review_dialog.finished.connect(self._review_finished)
        self.review_dialog.show()

    def _review_finished(self, *args):
        dialog = self.review_dialog
        self.review_dialog = None
        if dialog is not None:
            dialog.deleteLater()
        if self._close_pending:
            self.close()

    def closeEvent(self, event):
        if self.review_dialog is not None:
            self._close_pending = True
            self.review_dialog.close()
            event.ignore()
            return
        if self.worker is not None:
            self._close_pending = True
            self.cancel_analysis()
            event.ignore()
        else:
            event.accept()
