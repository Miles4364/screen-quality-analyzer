"""分页历史记录及已关联截图查看。"""
import hashlib
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QListWidget)
from storage.analysis_store import StorageError


class HistoryDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.offset = 0
        self.selected_task_id = None
        self.rows = []
        self.setWindowTitle('分析历史 · V0.4')
        self.resize(850, 500)
        layout = QVBoxLayout(self)
        self.status = QLabel('')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['保存时间', '视频', '处理帧数', '异常数'])
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
        for button in [self.previous, self.next, self.open_button]:
            row.addWidget(button)
        layout.addLayout(row)
        self.refresh()

    def page(self, delta):
        self.offset = max(0, self.offset + delta * 50)
        self.refresh()

    def refresh(self):
        try:
            records = self.store.list_tasks(51, self.offset)
            self.next.setEnabled(len(records) > 50)
            self.rows = records[:50]
            self.table.setRowCount(len(self.rows))
            for index, task in enumerate(self.rows):
                created = datetime.fromisoformat(task['created_at']).astimezone().strftime('%Y-%m-%d %H:%M:%S')
                for col, value in enumerate([created, task['filename'], task['processed_frames'], task['issue_count']]):
                    self.table.setItem(index, col, QTableWidgetItem(str(value)))
            self.status.setText(f'第 {self.offset // 50 + 1} 页 · 本页 {len(self.rows)} 条 · 时间按本机时区显示')
            self.previous.setEnabled(self.offset > 0)
            self.open_button.setEnabled(bool(self.rows))
            if self.rows:
                self.table.selectRow(0)
        except (StorageError, ValueError) as exc:
            self.rows = []
            self.table.setRowCount(0)
            self.open_button.setEnabled(False)
            self.next.setEnabled(False)
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
