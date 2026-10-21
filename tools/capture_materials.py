"""运行真实分析链路，采集当前桌面窗口用于使用说明。"""
import json
from pathlib import Path
from time import monotonic
from uuid import uuid4

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog

from gui.main_window import MainWindow
from gui.history_dialog import HistoryDialog, ScreenshotsDialog
from gui.issue_review_dialog import IssueReviewDialog
from gui.review_dialog import ReviewDialog


def capture_window(widget):
    """Windows 捕获本应用窗口，避免把其他应用通知写入材料。"""
    import sys
    if sys.platform != 'win32':
        screen = widget.screen()
        rect = widget.frameGeometry().intersected(screen.availableGeometry())
        return screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
    import ctypes
    from ctypes import wintypes
    from PySide6.QtGui import QImage, QPixmap
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user.GetWindowDC.restype = wintypes.HDC
    user.GetWindowDC.argtypes = [wintypes.HWND]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateDIBSection.restype = wintypes.HBITMAP
    gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    gdi.SelectObject.restype = wintypes.HANDLE
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    handle = int(widget.winId())
    rect = wintypes.RECT()
    if not user.GetWindowRect(handle, ctypes.byref(rect)):
        raise OSError('无法取得本应用窗口范围')
    width, height = rect.right - rect.left, rect.bottom - rect.top
    header = (ctypes.c_uint32 * 10)(40, width, (-height) & 0xffffffff,
                                   (32 << 16) | 1, 0, width * height * 4, 0, 0, 0, 0)
    pixels = ctypes.c_void_p()
    dc = user.GetWindowDC(handle)
    memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateDIBSection(dc, header, 0, ctypes.byref(pixels), None, 0)
    if not bitmap:
        gdi.DeleteDC(memory)
        user.ReleaseDC(handle, dc)
        raise OSError('无法创建窗口截图缓冲区')
    previous = gdi.SelectObject(memory, bitmap)
    try:
        if not user.PrintWindow(handle, memory, 2):
            raise OSError('Windows 未能捕获本应用窗口')
        data = ctypes.string_at(pixels, width * height * 4)
        image = QImage(data, width, height, width * 4, QImage.Format.Format_RGB32).copy()
        return QPixmap.fromImage(image)
    finally:
        gdi.SelectObject(memory, previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        user.ReleaseDC(handle, dc)


def start_capture(app, video_path, output_path):
    if app.platformName() == 'offscreen':
        raise RuntimeError('真实窗口截图需要可见桌面，不能使用 offscreen')
    source = Path(video_path)
    if not source.is_file():
        raise ValueError('请同时指定已有的视频样本路径')
    output = Path(output_path).resolve()
    output.mkdir(parents=True, exist_ok=True)
    run = output / ('run-' + uuid4().hex[:8])
    run.mkdir()
    window = MainWindow(str(source), database_path=run / 'analysis.sqlite3')
    window.showMaximized()
    state = {'ok': False, 'images': [], 'video': source.name,
             'capture': 'native window capture; Windows PrintWindow / QScreen elsewhere'}
    retained = []
    frames = []
    started = monotonic()

    def shot(name, target=window):
        target.raise_()
        target.activateWindow()
        app.processEvents()
        pixmap = capture_window(target)
        if pixmap.isNull():
            raise RuntimeError('系统未返回窗口截图')
        pixels = pixmap.toImage()
        colors = {pixels.pixelColor(pixels.width() * x // 8, pixels.height() * y // 8).rgb()
                  for x in range(1, 8) for y in range(1, 8)}
        if len(colors) < 2:
            raise RuntimeError('桌面截屏只有单色，请在可见的 Windows 桌面中重新运行')
        path = output / (name + '.png')
        if not pixmap.save(str(path)):
            raise OSError(f'截图无法写入：{path.name}')
        state['images'].append({'file': path.name, 'width': pixmap.width(), 'height': pixmap.height()})

    def pause(seconds=.8):
        deadline = monotonic() + seconds
        return lambda: monotonic() >= deadline

    def sequence():
        project = window.store.create_project('固定帧率验证')
        window.refresh_projects(project)
        window.task_title_edit.setText('1080p 黑屏与冻结验证')
        window.start_analysis()
        yield lambda: window.worker is None
        if window.result is None or window.task_id is None:
            raise RuntimeError(window.status_label.text())
        if not window.result.issues:
            raise RuntimeError('截图样本应包含黑屏或疑似冻结，避免生成空白结果材料')
        window.table.selectRow(0)
        yield pause()
        shot('fenxi_01')
        state.update(statistics=window.result.statistics, score=window.result.quality.score,
                     processed_frames=window.result.processed_frames)

        project_dialog = QInputDialog(window)
        retained.append(project_dialog)
        project_dialog.setWindowTitle('新建项目')
        project_dialog.setLabelText('项目名称（最多 80 字符）')
        project_dialog.setTextValue('复核样本归档')
        project_dialog.show()
        yield pause()
        shot('xiangmu_01', project_dialog)
        project_dialog.accept()
        project2 = window.store.create_project(project_dialog.textValue())
        window.refresh_projects(project)

        issue_dialog = IssueReviewDialog(window.store, window.task_id, 0, {}, window)
        retained.append(issue_dialog)
        issue_dialog.show()
        yield pause()
        shot('rengong_01', issue_dialog)
        issue_dialog.status_picker.setCurrentIndex(issue_dialog.status_picker.findData('CONFIRMED'))
        issue_dialog.note_edit.setPlainText('合成样本的流程验证记录，用于演示复核状态保存。')
        yield pause()
        shot('rengong_02', issue_dialog)
        issue_dialog.save()
        window.refresh_reviews()
        window.table.selectRow(0)
        yield pause()
        shot('fenxi_02')

        freeze_index = next((n for n, i in enumerate(window.result.issues) if i.issue_type == 'FREEZE'), 0)
        dialog = ReviewDialog(window.result, window.result.issues[freeze_index], window,
                              store=window.store, task_id=window.task_id, issue_ordinal=freeze_index)
        retained.append(dialog)
        frames.append(dialog)
        dialog.showMaximized()
        yield lambda: not dialog.busy and dialog.current_image is not None
        yield pause()
        shot('huamian_01', dialog)
        dialog.context_button.click()
        yield lambda: not dialog.busy and dialog.current_image is not None
        yield pause()
        shot('huamian_02', dialog)
        dialog.save_image(run / '异常前画面.png')
        dialog.next_button.click()
        yield lambda: not dialog.busy and dialog.current_image is not None
        yield pause()
        shot('huamian_03', dialog)
        dialog.close()
        yield lambda: not dialog.worker.isRunning()

        window.chart_nav.click()
        for index in range(window.charts.tabs.count()):
            window.charts.tabs.setCurrentIndex(index)
            yield pause()
            shot(f'tongji_{index + 1:02d}')
        window.analysis_nav.click()
        window.review_filter.setCurrentIndex(window.review_filter.findData('CONFIRMED'))
        window.table.selectRow(0)
        yield pause()
        shot('shaixuan_01')
        window.review_filter.setCurrentIndex(0)
        window.table.selectRow(freeze_index)
        yield pause()
        shot('shaixuan_02')

        history = HistoryDialog(window.store, window)
        retained.append(history)
        history.show()
        yield pause()
        shot('lishi_01', history)
        window.store.rename_task(window.task_id, '1080p 已完成画面复核')
        window.store.move_task(window.task_id, project2)
        history.reload_projects(project2)
        history.filter_changed()
        yield pause()
        shot('lishi_02', history)
        history.close()
        window.load_history(window.task_id)
        window.path_edit.blockSignals(True)
        window.path_edit.setText(str(source))
        window.path_edit.blockSignals(False)
        window.table.selectRow(0)
        yield pause()
        shot('lishi_03')

        shots = ScreenshotsDialog(window.store.list_screenshots(window.task_id), window)
        retained.append(shots)
        shots.show()
        yield pause()
        shot('jietu_01', shots)
        shots.close()
        window.export_report_to(run / '分析报告.xlsx', overwrite=False)
        yield lambda: window.worker is None
        if '报告已导出' not in window.status_label.text():
            raise RuntimeError(window.status_label.text())
        yield pause()
        shot('daochu_01')
        state['ok'] = True

    flow = sequence()
    waiting = None

    def finish(error=None):
        timer.stop()
        if error is not None:
            state['error'] = str(error)
        (output / 'capture.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        for dialog in frames:
            dialog.pause()
            dialog.worker.stop()
            dialog.worker.wait(5000)
        for widget in retained:
            widget.close()
        window.close()
        if window.worker is None:
            app.quit()

    def tick():
        nonlocal waiting
        try:
            if monotonic() - started > 300:
                raise TimeoutError('截图验证超时')
            if waiting is not None and not waiting():
                return
            waiting = next(flow)
        except StopIteration:
            finish()
        except Exception as exc:
            finish(exc)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    app.exec()
    return 0 if state['ok'] else 1
