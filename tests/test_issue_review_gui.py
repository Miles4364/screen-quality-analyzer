import pytest
pytest.importorskip('PySide6')
from tests.test_gui import window
from tests.test_storage import result
from core.models import DetectedIssue
from gui.issue_review_dialog import IssueReviewDialog
from storage.analysis_store import StorageError


def test_review_filter_history_and_failure(app,window,result,monkeypatch):
    result.issues.append(DetectedIssue('FREEZE',2,3,1,'MEDIUM','静态 PPT'))
    window._show_result(result)
    task_id = window.task_id
    score = window.result.quality
    dialog = IssueReviewDialog(window.store,task_id,1,{},window)
    dialog.status_picker.setCurrentIndex(2)
    dialog.note_edit.setPlainText('静态 PPT，非设备冻结')
    original = window.store.save_review
    def fail(*args):
        raise StorageError('模拟保存失败')
    monkeypatch.setattr(window.store,'save_review',fail)
    dialog.save()
    assert '失败' in dialog.message.text()
    assert dialog.note_edit.toPlainText() == '静态 PPT，非设备冻结'
    monkeypatch.setattr(window.store,'save_review',original)
    dialog.save()
    window.load_history(task_id)
    assert window.table.item(1,6).text() == '误报'
    assert window.result.quality == score
    window.review_filter.setCurrentIndex(3)
    assert window.table.isRowHidden(0)
    assert not window.table.isRowHidden(1)
    assert window.table.currentRow() == -1
    window.table.selectRow(1)
    assert window.table.currentRow() == 1
    window.review_filter.setCurrentIndex(2)
    assert all(window.table.isRowHidden(i) for i in range(2))
    window.open_review()
    assert '没有异常' in window.status_label.text()
    window.path_edit.setText('another.mp4')
    assert not window.edit_review_button.isEnabled()
    assert not window.review_summary.text()
