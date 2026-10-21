"""工作台使用同一份历史数据，图表按真实区间计算，不伪造空状态。"""
from dataclasses import asdict
import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from gui.analysis_charts import AnalysisCharts, prepare_chart_data
from core.models import DetectedIssue
from tests.test_gui import window
from tests.test_storage import result


def test_chart_intervals_deduplicate_and_keep_review_independent(result):
    result.analyzed_duration = 60
    result.issues = [
        DetectedIssue('BLACK_SCREEN', 0, 20, 20, 'HIGH', 'a'),
        DetectedIssue('BLACK_SCREEN', 10, 30, 20, 'HIGH', 'b'),
        DetectedIssue('FREEZE', 20, 40, 20, 'HIGH', 'c'),
        DetectedIssue('FREEZE', 30, 40, 10, 'HIGH', 'd'),
    ]
    before = asdict(result)
    data = prepare_chart_data(result, [{'issue_ordinal': 0, 'status': 'FALSE_POSITIVE'},
                                      {'issue_ordinal': 2, 'status': 'CONFIRMED'}])
    assert data.available and len(data.events) == 4
    assert data.composition == [('黑屏', 30), ('非黑屏疑似冻结', 10), ('其余已分析时长', 20)]
    assert data.reviews == [('待复核', 2), ('确认异常', 1), ('误报', 1)]
    assert asdict(result) == before


def test_chart_empty_and_invalid_result_are_distinct(result):
    assert not prepare_chart_data(None).available
    result.issues = []
    data = prepare_chart_data(result)
    assert data.available and data.events == []
    assert data.composition[-1][1] == result.analyzed_duration
    assert sum(count for _, count in data.reviews) == 0
    result.analyzed_duration = 0
    assert not prepare_chart_data(result).available


def test_chart_clips_events_to_analyzed_range(result):
    result.issues = [
        DetectedIssue('FREEZE', -2, 1, 3, 'HIGH', 'before'),
        DetectedIssue('FREEZE', 2, 5, 3, 'HIGH', 'after'),
    ]
    data = prepare_chart_data(result)
    assert data.events == [(0, 'FREEZE', 0, 1), (1, 'FREEZE', 2, 3)]
    assert data.composition[1][1] == 2


def test_workspace_navigation_and_chart_paint(window, app, result):
    window._show_result(result, persist=False)
    window.chart_nav.click()
    assert window.workspace_stack.currentIndex() == 1
    assert window.charts.tabs.count() == 4
    for index, name in enumerate(AnalysisCharts.TAB_NAMES):
        window.charts.tabs.setCurrentIndex(index)
        app.processEvents()
        assert window.charts.tabs.tabText(index) == name
        assert not window.charts.canvases[index].grab().isNull()
    window.analysis_nav.click()
    assert window.workspace_stack.currentIndex() == 0
    assert window.table.rowCount() == 1


def test_task_tree_loads_saved_result_and_review_detail(window, result):
    project = window.store.create_project('会议室 A')
    task = window.store.save_result(result, title='现场测试', project_id=project)
    window.store.save_review(task, 0, 'CONFIRMED', '已比对录制画面')
    window.refresh_projects()
    group = next(window.project_tree.topLevelItem(i) for i in range(window.project_tree.topLevelItemCount())
                 if window.project_tree.topLevelItem(i).text(0) == '会议室 A')
    window._select_tree_project(group)
    assert window.project_picker.currentData() == project
    node = group.child(0)
    assert node.text(0) == '现场测试'
    window.project_tree.itemActivated.emit(node, 0)
    assert window.task_id == task
    assert window.table.rowCount() == 1
    window.table.selectRow(0)
    assert '已比对录制画面' in window.detail_label.text()
    assert '确认异常' in window.detail_label.text()
    assert window.charts.data.reviews == [('待复核', 0), ('确认异常', 1), ('误报', 0)]
    assert len(window.store.list_tasks()) == 1


def test_changing_source_clears_charts_and_event_detail(window, result, tmp_path):
    window._show_result(result, persist=False)
    window.table.selectRow(0)
    assert window.charts.data.available
    window.path_edit.setText(str(tmp_path / 'next.mp4'))
    assert not window.charts.data.available
    assert '选择视频' in window.detail_label.text()
    assert '事件 1' not in window.detail_label.text()


def test_filter_clears_detail_and_busy_disables_task_switch(window, result):
    window._show_result(result)
    window.table.selectRow(0)
    assert '事件 1' in window.detail_label.text()
    window.review_filter.setCurrentIndex(window.review_filter.findData('CONFIRMED'))
    assert window.table.isRowHidden(0)
    assert '事件 1' not in window.detail_label.text()
    window._set_busy(True)
    assert not window.project_tree.isEnabled()
    assert not window.refresh_tree_button.isEnabled()
    window._set_busy(False)
    assert window.project_tree.isEnabled()


def test_long_names_do_not_expand_workspace_and_report_path_is_in_tooltip(window, app, result, tmp_path):
    project = window.store.create_project('会议室' * 25)
    window.refresh_projects(project)
    result.video_metadata.filename = 'long_recording_name_' * 12 + '.mp4'
    window._show_metadata(result.video_metadata)
    window._show_result(result, persist=False)
    window.resize(1100, 720)
    app.processEvents()
    assert window.width() == 1100
    assert window.project_picker.width() <= 200
    assert window.start_button.isVisible() and window.export_button.isVisible()
    target = tmp_path / '报告.xlsx'
    window._report_ready(str(target))
    assert window.status_label.text() == '报告已导出：报告.xlsx'
    assert window.status_label.toolTip() == str(target)


def test_same_source_history_tasks_refresh_chart_reviews(window, result):
    first = window.store.save_result(result, title='第一次')
    second = window.store.save_result(result, title='第二次')
    window.store.save_review(first, 0, 'CONFIRMED', '第一轮人工复核')
    window.load_history(first)
    assert window.charts.data.reviews[1] == ('确认异常', 1)
    window.load_history(second)
    assert window.charts.data.reviews == [('待复核', 1), ('确认异常', 0), ('误报', 0)]
    window.table.selectRow(0)
    assert '第一轮人工复核' not in window.detail_label.text()
