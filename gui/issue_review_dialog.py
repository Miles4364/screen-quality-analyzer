from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPlainTextEdit, QPushButton
from core.review import REVIEW_LABELS
from storage.analysis_store import StorageError


class IssueReviewDialog(QDialog):
    def __init__(self, store, task_id, ordinal, record, parent=None):
        super().__init__(parent)
        self.store, self.task_id, self.ordinal = store, task_id, ordinal
        self.setWindowTitle(f'异常 #{ordinal+1} 人工复核')
        self.resize(520, 350)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('记录人工判断；不修改检测事件和自动评分。'))
        self.status_picker = QComboBox()
        for key, label in REVIEW_LABELS.items():
            self.status_picker.addItem(label, key)
        self.status_picker.setCurrentIndex(self.status_picker.findData(record.get('status', 'PENDING')))
        layout.addWidget(self.status_picker)
        layout.addWidget(QLabel('备注（最多 2000 字符）'))
        self.note_edit = QPlainTextEdit(record.get('note', ''))
        layout.addWidget(self.note_edit)
        self.message = QLabel('最近保存：' + record.get('updated_at', '尚未复核'))
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        button = QPushButton('保存复核结论')
        button.clicked.connect(self.save)
        layout.addWidget(button)

    def save(self):
        try:
            self.store.save_review(self.task_id, self.ordinal, self.status_picker.currentData(), self.note_edit.toPlainText())
        except StorageError as exc:
            self.message.setText(str(exc))
            return
        self.accept()
