import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtGui import QImage
from gui.main_window import MainWindow
from gui.history_dialog import HistoryDialog, ScreenshotsDialog
from storage.analysis_store import AnalysisStore, StorageError
from tests.test_gui import window, wait_until
from tests.test_review import result, settled


def test_auto_save_and_history_reload(app, window, result):
    window._show_result(result)
    assert window.task_id
    assert not window.save_result_button.isEnabled()
    task_id = window.task_id
    reopened = MainWindow(database_path=window.store.path)
    try:
        reopened.load_history(task_id)
        assert reopened.table.rowCount() == 2
        assert reopened.review_button.isEnabled()
        assert reopened.task_id == task_id
        assert len(reopened.store.list_tasks()) == 1
    finally:
        reopened.close()


def test_save_failure_retry_and_cancel(window, result, monkeypatch):
    original = window.store.save_result
    def fail(*args, **kwargs):
        raise StorageError('模拟写入失败')
    monkeypatch.setattr(window.store, 'save_result', fail)
    window._show_result(result)
    assert window.result is result
    assert window.task_id is None
    assert window.save_result_button.isEnabled()
    monkeypatch.setattr(window.store, 'save_result', original)
    window.save_result()
    window.save_result()
    assert len(window.store.list_tasks()) == 1
    window._cancel_requested = True
    window._show_result(result)
    assert len(window.store.list_tasks()) == 1


def test_screenshot_association_reopened(app, window, result, tmp_path):
    window._show_result(result)
    window.table.selectRow(1)
    window.open_review()
    review = window.review_dialog
    settled(app, review, 60)
    target = tmp_path / '截图.png'
    review.save_image(target)
    rows = AnalysisStore(window.store.path).list_screenshots(window.task_id)
    assert len(rows) == 1 and rows[0]['issue_ordinal'] == 1
    assert rows[0]['frame_index'] == 60
    dialog = ScreenshotsDialog(rows)
    assert not dialog.preview.pixmap().isNull()
    target.unlink()
    dialog.show_screenshot(0)
    assert '不存在' in dialog.status.text()
    dialog.close()
    review.close()
    wait_until(app, lambda: window.review_dialog is None)


def test_missing_source_history_keeps_results(app, window, result):
    from pathlib import Path
    window._show_result(result)
    task_id = window.task_id
    Path(result.video_metadata.filepath).unlink()
    window.load_history(task_id)
    assert window.table.rowCount() == 2
    assert not window.review_button.isEnabled()
    window.open_review()
    assert window.review_dialog is None
    assert window.screenshots_button.isEnabled()


def test_history_dialog_selection(window, result):
    window._show_result(result)
    dialog = HistoryDialog(window.store)
    assert dialog.table.rowCount() == 1
    dialog.open_selected()
    assert dialog.selected_task_id == window.task_id
    dialog.close()


def test_screenshot_association_failure_keeps_file(app, window, result, tmp_path, monkeypatch):
    window._show_result(result)
    window.open_review()
    review = window.review_dialog
    settled(app, review, 30)
    def fail(*args, **kwargs):
        raise StorageError('模拟数据库锁定')
    monkeypatch.setattr(window.store, 'add_screenshot', fail)
    target = tmp_path / 'kept.png'
    with pytest.raises(StorageError, match='文件已保存'):
        review.save_image(target)
    assert not QImage(str(target)).isNull()
    review.close()
    wait_until(app, lambda: window.review_dialog is None)


def test_modified_screenshot_not_silently_shown(app, window, result, tmp_path):
    window._show_result(result)
    path = tmp_path / 'modified.png'
    path.write_bytes(b'original')
    window.store.add_screenshot(window.task_id, 0, path, 30, 1)
    records = window.store.list_screenshots(window.task_id)
    path.write_bytes(b'replaced')
    dialog = ScreenshotsDialog(records)
    assert '已更改' in dialog.status.text()
    dialog.close()
