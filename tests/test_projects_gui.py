import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QInputDialog
from gui.history_dialog import HistoryDialog
from tests.test_gui import window, wait_until
from tests.test_review import result


def test_project_task_selection_on_analysis(app, window, result, monkeypatch):
    project = window.store.create_project('测试项目')
    window.refresh_projects(project)
    window.path_edit.setText(result.video_metadata.filepath)
    window.task_title_edit.setText('自定义任务')
    monkeypatch.setattr('gui.worker.AnalysisEngine.analyze',lambda *args, **kwargs: result)
    window.start_analysis()
    assert not window.project_picker.isEnabled()
    wait_until(app,lambda: window.worker is None)
    saved = window.store.load_task(window.task_id)
    assert saved['title'] == '自定义任务'
    assert saved['project_id'] == project
    window.load_history(window.task_id)
    assert window.task_title_edit.text() == '自定义任务'
    assert window.project_picker.currentData() == project


def test_history_management_and_filter_reset(app, window, result, monkeypatch):
    first = window.store.create_project('A')
    second = window.store.create_project('B')
    task = window.store.save_result(result, title='old', project_id=first)
    dialog = HistoryDialog(window.store)
    try:
        dialog.project_filter.setCurrentIndex(dialog.project_filter.findData(first))
        assert dialog.table.rowCount() == 1
        monkeypatch.setattr(QInputDialog,'getText',lambda *args, **kwargs: ('renamed',True))
        dialog.rename_task()
        assert dialog.rows[0]['title'] == 'renamed'
        dialog.rename_project()
        assert dialog.project_filter.currentText() == 'renamed'
        monkeypatch.setattr(QInputDialog,'getItem',lambda *args, **kwargs: ('项目：B',True))
        dialog.move_task()
        assert dialog.table.rowCount() == 0
        assert window.store.load_task(task)['project_id'] == second
        dialog.project_filter.setCurrentIndex(dialog.project_filter.findData(second))
        dialog.offset = 50
        dialog.search_edit.setText('renamed')
        dialog.filter_changed()
        assert dialog.offset == 0 and dialog.table.rowCount() == 1
        dialog.search_edit.setText('absent')
        dialog.filter_changed()
        assert dialog.table.rowCount() == 0
    finally:
        dialog.close()


def test_create_project_from_main(window, monkeypatch):
    monkeypatch.setattr(QInputDialog,'getText',lambda *args, **kwargs: ('新项目',True))
    window.create_project()
    assert window.project_picker.currentText() == '新项目'
    window.create_project()
    assert len(window.store.list_projects()) == 1
    assert '失败' in window.status_label.text()
