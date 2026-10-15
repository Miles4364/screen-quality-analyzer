"""分页历史记录及已关联截图查看。"""
import hashlib
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QListWidget, QComboBox, QLineEdit, QInputDialog)
from storage.analysis_store import StorageError


class HistoryDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.offset = 0
        self.selected_task_id = None
        self.rows = []
        self.setWindowTitle('项目与任务 · V0.5')
        self.resize(1050, 560)
        layout = QVBoxLayout(self)
        self.status = QLabel('')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        filters = QHBoxLayout()
        self.project_filter = QComboBox()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('按任务名或视频文件名搜索')
        self.search_button = QPushButton('搜索')
        self.create_button = QPushButton('新建项目')
        self.rename_project_button = QPushButton('重命名项目')
        for widget in [self.project_filter, self.search_edit, self.search_button, self.create_button, self.rename_project_button]:
            filters.addWidget(widget)
        layout.addLayout(filters)
        self.project_filter.currentIndexChanged.connect(self.filter_changed)
        self.search_button.clicked.connect(self.filter_changed)
        self.search_edit.returnPressed.connect(self.filter_changed)
        self.create_button.clicked.connect(self.create_project)
        self.rename_project_button.clicked.connect(self.rename_project)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['保存时间', '任务', '项目', '视频', '帧数', '异常数'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.open_selected)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        self.previous = QPushButton('上一页')
        self.next = QPushButton('下一页')
        self.open_button = QPushButton('打开选中结果')
        self.previous.clicked.connect(lambda: self.page(-1))
        self.next.clicked.connect(lambda: self.page(1))
        self.open_button.clicked.connect(self.open_selected)
        self.rename_task_button = QPushButton('重命名任务')
        self.move_button = QPushButton('移动任务')
        self.rename_task_button.clicked.connect(self.rename_task)
        self.move_button.clicked.connect(self.move_task)
        for button in [self.previous, self.next, self.rename_task_button, self.move_button, self.open_button]:
            row.addWidget(button)
        layout.addLayout(row)
        self.reload_projects()
        self.refresh()

    def page(self, delta):
        self.offset = max(0, self.offset + delta * 50)
        self.refresh()

    def refresh(self):
        try:
            records = self.store.list_tasks(51, self.offset, project_id=self.project_filter.currentData(), search=self.search_edit.text())
            self.next.setEnabled(len(records) > 50)
            self.rows = records[:50]
            self.table.setRowCount(len(self.rows))
            for index, task in enumerate(self.rows):
                created = datetime.fromisoformat(task['created_at']).astimezone().strftime('%Y-%m-%d %H:%M:%S')
                for col, value in enumerate([created, task['title'], task['project_name'] or '未分组', task['filename'], task['processed_frames'], task['issue_count']]):
                    self.table.setItem(index, col, QTableWidgetItem(str(value)))
            self.status.setText(f'第 {self.offset // 50 + 1} 页 · 本页 {len(self.rows)} 条 · 时间按本机时区显示')
            self.previous.setEnabled(self.offset > 0)
            self.open_button.setEnabled(bool(self.rows))
            self.rename_task_button.setEnabled(bool(self.rows))
            self.move_button.setEnabled(bool(self.rows))
            if self.rows:
                self.table.selectRow(0)
        except (StorageError, ValueError) as exc:
            self.rows = []
            self.table.setRowCount(0)
            self.open_button.setEnabled(False)
            self.next.setEnabled(False)
            self.rename_task_button.setEnabled(False)
            self.move_button.setEnabled(False)
            self.status.setText(str(exc))

    def reload_projects(self, selected='all'):
        self.project_filter.blockSignals(True)
        self.project_filter.clear()
        self.project_filter.addItem('全部项目', 'all')
        self.project_filter.addItem('未分组', None)
        try:
            for project in self.store.list_projects():
                self.project_filter.addItem(project['name'], project['id'])
        except StorageError as exc:
            self.status.setText(str(exc))
        index = self.project_filter.findData(selected)
        self.project_filter.setCurrentIndex(max(0, index))
        self.project_filter.blockSignals(False)
        self.rename_project_button.setEnabled(self.project_filter.currentData() not in ('all', None))

    def filter_changed(self, *args):
        self.offset = 0
        self.rename_project_button.setEnabled(self.project_filter.currentData() not in ('all', None))
        self.refresh()

    def create_project(self):
        name, accepted = QInputDialog.getText(self, '新建项目', '项目名称（最多 80 字符）')
        if accepted:
            try:
                project_id = self.store.create_project(name)
                self.reload_projects(project_id)
                self.filter_changed()
            except StorageError as exc:
                self.status.setText(str(exc))

    def rename_project(self):
        project_id = self.project_filter.currentData()
        if project_id in ('all', None):
            return
        name, accepted = QInputDialog.getText(self, '重命名项目', '项目名称', text=self.project_filter.currentText())
        if accepted:
            try:
                self.store.rename_project(project_id, name)
                self.reload_projects(project_id)
                self.refresh()
            except StorageError as exc:
                self.status.setText(str(exc))

    def selected_task(self):
        row = self.table.currentRow()
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def rename_task(self):
        task = self.selected_task()
        if task is None:
            return
        title, accepted = QInputDialog.getText(self, '重命名任务', '任务名称（最多 120 字符）', text=task['title'])
        if accepted:
            try:
                self.store.rename_task(task['id'], title)
                self.refresh()
            except StorageError as exc:
                self.status.setText(str(exc))

    def move_task(self):
        task = self.selected_task()
        if task is None:
            return
        try:
            projects = self.store.list_projects()
            labels = ['未分组'] + ['项目：' + p['name'] for p in projects]
            ids = [None] + [p['id'] for p in projects]
            label, accepted = QInputDialog.getItem(self, '移动任务', '目标项目', labels,
                                                 current=ids.index(task['project_id']) if task['project_id'] in ids else 0,
                                                 editable=False)
            if accepted:
                self.store.move_task(task['id'], ids[labels.index(label)])
                self.offset = 0
                self.refresh()
        except StorageError as exc:
            self.status.setText(str(exc))

    def open_selected(self, *args):
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            self.selected_task_id = self.rows[row]['id']
            self.accept()


class ScreenshotsDialog(QDialog):
    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.records = records
        self.setWindowTitle('已保存截图')
        self.resize(850, 650)
        layout = QVBoxLayout(self)
        self.items = QListWidget()
        self.items.setMaximumHeight(140)
        for record in records:
            self.items.addItem(f'异常 {record["issue_ordinal"] + 1} · {record["timestamp"]:.3f} 秒 · {Path(record["path"]).name}')
        layout.addWidget(self.items)
        self.preview = QLabel('暂无截图')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(320, 180)
        layout.addWidget(self.preview, 1)
        self.status = QLabel('')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.items.currentRowChanged.connect(self.show_screenshot)
        if records:
            self.items.setCurrentRow(0)

    def show_screenshot(self, row):
        if not 0 <= row < len(self.records):
            return
        path = self.records[row]['path']
        try:
            content = Path(path).read_bytes()
            if hashlib.sha256(content).hexdigest() != self.records[row]['sha256']:
                self.preview.clear()
                self.status.setText(f'截图内容已更改，无法作为原记录查看：{path}')
                return
        except OSError:
            content = b''
        pixmap = QPixmap()
        pixmap.loadFromData(content)
        if pixmap.isNull():
            self.preview.clear()
            self.status.setText(f'截图不存在或无法读取：{path}')
        else:
            self.preview.setPixmap(pixmap.scaled(780, 420, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.status.setText(path)
