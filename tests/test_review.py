import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import shutil
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage
from core.analysis_engine import AnalysisEngine
from gui.review_dialog import ReviewDialog
from tools.generate_samples import generate
from tests.test_gui import window, wait_until


@pytest.fixture
def result(tmp_path):
    if not shutil.which("ffprobe"):
        pytest.skip("需要 FFprobe")
    path = generate(tmp_path / '复核.mp4', duration=4, black=((1, 2),), freeze=((2, 3),))
    return AnalysisEngine().analyze(str(path))


@pytest.fixture
def dialog(app, result):
    d = ReviewDialog(result, result.issues[0])
    d.show()
    yield d
    d.close()
    wait_until(app, lambda: not d.worker.isRunning())
    app.processEvents()


def settled(app, dialog, index):
    wait_until(app, lambda: not dialog.busy and dialog.current_frame is not None and dialog.current_frame.index == index)


def test_initial_snapshot_seek_and_save(app, dialog, tmp_path):
    settled(app, dialog, 30)
    assert dialog.current_image.width() == 640
    assert dialog.current_image.pixelColor(100, 100).red() < 5
    output = tmp_path / '截图 中文.png'
    dialog.save_image(output)
    saved = QImage(str(output))
    assert saved.width() == 640 and saved.height() == 360
    QTest.mouseClick(dialog.context_button, Qt.MouseButton.LeftButton)
    settled(app, dialog, 0)
    QTest.mouseClick(dialog.next_button, Qt.MouseButton.LeftButton)
    settled(app, dialog, 1)
    QTest.mouseClick(dialog.previous_button, Qt.MouseButton.LeftButton)
    settled(app, dialog, 0)
    QTest.mouseClick(dialog.jump_button, Qt.MouseButton.LeftButton)
    settled(app, dialog, 30)
    with pytest.raises(OSError):
        dialog.save_image(tmp_path / 'absent' / 'out.png')


def test_latest_seek_wins(app, dialog):
    for index in [0, 110, 10, 60, 90]:
        dialog.seek_frame(index)
    settled(app, dialog, 90)
    assert dialog.slider.value() == 90
    dialog.show_error(dialog.token - 1, 'stale error')
    assert dialog.current_frame.index == 90


def test_playback_pause_and_end(app, dialog):
    settled(app, dialog, 30)
    dialog.toggle_play()
    wait_until(app, lambda: dialog.current_frame.index >= 33)
    dialog.toggle_play()
    assert not dialog.playing
    dialog.seek_frame(118)
    settled(app, dialog, 118)
    dialog.toggle_play()
    wait_until(app, lambda: dialog.current_frame.index == 119 and not dialog.playing)
    assert dialog.save_button.isEnabled()


def test_escape_shutdown(app, dialog):
    dialog.seek_frame(100)
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(app, lambda: not dialog.worker.isRunning() and not dialog.isVisible())


def test_main_window_review_lifecycle(app, window, result):
    window._show_result(result)
    window.table.selectRow(1)
    QTest.mouseClick(window.review_button, Qt.MouseButton.LeftButton)
    review = window.review_dialog
    settled(app, review, 60)
    stopped = []
    review.worker.finished.connect(lambda: stopped.append(True))
    window.close()
    wait_until(app, lambda: window.review_dialog is None)
    assert stopped
    assert not window.isVisible()


def test_read_failure_disables_export(app, dialog, monkeypatch):
    settled(app, dialog, 30)
    def fail(index):
        raise RuntimeError('模拟解码失败')
    monkeypatch.setattr(dialog.worker.extractor, 'read', fail)
    dialog.seek_frame(50)
    wait_until(app, lambda: not dialog.busy)
    assert dialog.current_image is None
    assert not dialog.save_button.isEnabled()
    assert '模拟解码失败' in dialog.status.text()
