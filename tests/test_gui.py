"""Qt 事件循环与真实后台线程测试；基础 CLI 环境可跳过 GUI 测试。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import shutil
import time
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from exceptions.video_exception import AnalysisCancelled
from tools.generate_samples import generate


def wait_until(app, condition, timeout=10000):
    deadline = time.monotonic() + timeout / 1000
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert condition(), 'GUI state did not settle before timeout'


@pytest.fixture
def window(app, tmp_path):
    w = MainWindow(database_path=tmp_path / 'gui.sqlite3')
    w.show()
    yield w
    if w.worker is not None:
        w.cancel_analysis()
        wait_until(app, lambda: w.worker is None)
    w.close()
    w.deleteLater()
    app.processEvents()


@pytest.mark.skipif(not shutil.which('ffprobe'), reason='需要 FFprobe')
def test_real_analysis_and_repeat(window, app, tmp_path):
    path = generate(tmp_path / '中文 GUI.mp4', duration=4, black=((1, 2),), freeze=((2, 3),))
    window.path_edit.setText(str(path))
    QTest.mouseClick(window.start_button, Qt.MouseButton.LeftButton)
    assert not window.start_button.isEnabled()
    assert not window.browse_button.isEnabled()
    wait_until(app, lambda: window.worker is None)
    assert window.result.statistics['total_count'] == 2
    assert window.table.rowCount() == 2
    assert window.progress_bar.value() == 100
    assert '中文 GUI.mp4' in window.metadata_label.text()
    QTest.mouseClick(window.start_button, Qt.MouseButton.LeftButton)
    wait_until(app, lambda: window.worker is None)
    assert window.table.rowCount() == 2
    window.path_edit.setText(str(tmp_path / 'different.mp4'))
    assert window.table.rowCount() == 0
    assert window.result is None


def test_missing_file(window):
    window.start_analysis()
    assert window.worker is None
    assert '有效' in window.status_label.text()


def test_background_error(window, app, tmp_path, monkeypatch):
    path = tmp_path / 'bad.mp4'
    path.write_text('not video')
    def fail(*args, **kwargs):
        raise RuntimeError('测试解码失败')
    monkeypatch.setattr('gui.worker.AnalysisEngine.analyze', fail)
    window.path_edit.setText(str(path))
    window.start_analysis()
    wait_until(app, lambda: window.worker is None)
    assert window.start_button.isEnabled()
    assert '失败' in window.status_label.text()
    assert window.result is None


@pytest.mark.parametrize('close', [False, True])
def test_responsive_cancel_and_close(window, app, tmp_path, monkeypatch, close):
    path = tmp_path / 'slow.mp4'
    path.touch()
    def slow(self, path, *, should_cancel, **kwargs):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if should_cancel():
                raise AnalysisCancelled()
            time.sleep(.005)
        raise RuntimeError('test cancellation did not arrive')
    monkeypatch.setattr('gui.worker.AnalysisEngine.analyze', slow)
    window.path_edit.setText(str(path))
    window.start_analysis()
    ticks = []
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    wait_until(app, lambda: len(ticks) >= 3)
    if close:
        window.close()
    else:
        QTest.mouseClick(window.cancel_button, Qt.MouseButton.LeftButton)
    wait_until(app, lambda: window.worker is None)
    timer.stop()
    assert window.result is None
    assert window.table.rowCount() == 0
    assert '取消' in window.status_label.text()
    assert window.start_button.isEnabled()
    if close:
        assert not window.isVisible()


def test_cancel_queued_result(window):
    window._cancel_requested = True
    window._show_result(object())
    assert window.result is None
    assert '取消' in window.status_label.text()
