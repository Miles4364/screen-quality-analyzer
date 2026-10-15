"""Qt 应用贯穿会话，每个 GUI 测试结束前销毁窗口并等待线程退出。"""
import os
import pytest


@pytest.fixture(scope='session')
def app():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    instance = QApplication.instance() or QApplication([])
    instance.setQuitOnLastWindowClosed(False)
    yield instance


@pytest.fixture(autouse=True)
def cleanup_qt_windows(request):
    yield
    if 'app' not in request.fixturenames:
        return
    from PySide6.QtCore import QCoreApplication, QEvent, QThread
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid
    import gc
    instance = QApplication.instance()
    if instance is None:
        return
    widgets = instance.topLevelWidgets()
    for widget in widgets:
        if isValid(widget):
            widget.close()
            for thread in widget.findChildren(QThread):
                assert thread.wait(5000), 'GUI test left a decoder thread running'
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    instance.processEvents()
    gc.collect()
