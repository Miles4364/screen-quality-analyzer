"""异常复核：精确帧截图、定位、静音播放及 PNG 导出。"""
import math
from time import monotonic
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QDialog, QLabel, QPushButton, QSlider,
                              QVBoxLayout, QHBoxLayout, QFileDialog)
from gui.review_worker import ReviewWorker
from storage.analysis_store import StorageError
from utils.time_util import seconds_to_time


class ReviewDialog(QDialog):
    def __init__(self, result, issue, parent=None, *, store=None, task_id=None, issue_ordinal=None):
        super().__init__(parent)
        self.setWindowTitle('异常画面复核 · V0.9.2')
        self.resize(900, 650)
        self.setMinimumSize(640, 480)
        self.store = store
        self.task_id = task_id
        self.issue_ordinal = issue_ordinal
        self.fps = result.video_metadata.fps
        self.count = result.processed_frames
        self.issue = issue
        self.token = 0
        self.current_frame = None
        self.current_image = None
        self.busy = False
        self.closing = False
        self.playing = False
        self.origin = 0
        self.started = 0
        layout = QVBoxLayout(self)
        kind = '黑屏' if issue.issue_type == 'BLACK_SCREEN' else '疑似冻结'
        self.info = QLabel(f'{kind}  {seconds_to_time(issue.start_time)} → {seconds_to_time(issue.end_time)}')
        layout.addWidget(self.info)
        self.image_label = QLabel('正在提取异常画面…')
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(320, 180)
        self.image_label.setStyleSheet('background: #172231; color: white;')
        layout.addWidget(self.image_label, 1)
        self.status = QLabel('')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, self.count - 1)
        self.slider.setAccessibleName('视频帧位置')
        self.slider.sliderPressed.connect(self.pause)
        self.slider.valueChanged.connect(self.seek_frame)
        layout.addWidget(self.slider)
        row = QHBoxLayout()
        self.play_button = QPushButton('播放（静音）')
        self.play_button.clicked.connect(self.toggle_play)
        self.previous_button = QPushButton('上一帧')
        self.previous_button.clicked.connect(lambda: self.step(-1))
        self.next_button = QPushButton('下一帧')
        self.next_button.clicked.connect(lambda: self.step(1))
        self.jump_button = QPushButton('跳到异常开始')
        self.jump_button.clicked.connect(lambda: self.seek_time(issue.start_time))
        self.context_button = QPushButton('查看前 2 秒')
        self.context_button.clicked.connect(lambda: self.seek_time(max(0, issue.start_time - 2)))
        self.save_button = QPushButton('保存当前截图')
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_dialog)
        for button in [self.play_button, self.previous_button, self.next_button, self.jump_button, self.context_button, self.save_button]:
            row.addWidget(button)
        layout.addLayout(row)
        hint = QLabel('截图保留原始分辨率。静音播放用于画面复核；静态 PPT 仍需人工判断。')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.tick)
        self.worker = ReviewWorker(result.video_metadata.filepath, self.fps, self.count, self)
        self.worker.ready.connect(self.show_frame)
        self.worker.failed.connect(self.show_error)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()
        self.seek_time(issue.start_time)

    def pause(self):
        self.playing = False
        self.timer.stop()
        self.play_button.setText('播放（静音）')
        self.save_button.setEnabled(self.current_image is not None and not self.busy)

    def seek_time(self, seconds):
        self.seek_frame(min(self.count - 1, max(0, math.floor(seconds * self.fps + 1e-6))))

    def seek_frame(self, index):
        self.pause()
        self.request(index)

    def step(self, delta):
        index = self.current_frame.index if self.current_frame is not None else self.slider.value()
        self.seek_frame(min(self.count - 1, max(0, index + delta)))

    def request(self, index):
        if self.closing:
            return
        self.token += 1
        self.busy = True
        self.save_button.setEnabled(False)
        self.status.setText(f'正在读取 {seconds_to_time(index / self.fps)}…')
        self.worker.request(self.token, index)

    @Slot(int, object)
    def show_frame(self, token, frame):
        if self.closing or token != self.token:
            return
        self.busy = False
        self.current_frame = frame
        rgb = frame.image[:, :, ::-1].copy()
        self.current_image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()
        self.render_image()
        self.slider.blockSignals(True)
        self.slider.setValue(frame.index)
        self.slider.blockSignals(False)
        self.status.setText(f'{seconds_to_time(frame.timestamp)} · 第 {frame.index + 1} / {self.count} 帧 · {rgb.shape[1]}×{rgb.shape[0]}')
        self.save_button.setEnabled(not self.playing)
        if frame.index == self.count - 1:
            self.pause()
            self.save_button.setEnabled(True)

    def render_image(self):
        if self.current_image is not None:
            self.image_label.setPixmap(QPixmap.fromImage(self.current_image).scaled(
                self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render_image()

    @Slot(int, str)
    def show_error(self, token, message):
        if token != self.token or self.closing:
            return
        self.pause()
        self.busy = False
        self.current_frame = None
        self.current_image = None
        self.image_label.clear()
        self.status.setText(f'读取失败：{message}')
        self.save_button.setEnabled(False)

    def toggle_play(self):
        if self.playing:
            self.pause()
            self.save_button.setEnabled(self.current_image is not None and not self.busy)
            return
        if self.busy or self.current_frame is None:
            return
        self.origin = self.current_frame.index
        if self.origin == self.count - 1:
            self.origin = 0
        self.started = monotonic()
        self.playing = True
        self.play_button.setText('暂停')
        self.save_button.setEnabled(False)
        self.timer.start()

    def tick(self):
        if not self.busy:
            index = min(self.count - 1, self.origin + int((monotonic() - self.started) * self.fps))
            if self.current_frame is None or index != self.current_frame.index:
                self.request(index)

    def save_image(self, path):
        if self.current_image is None or self.busy or self.playing:
            raise ValueError('请先暂停并等待画面加载完成')
        if not self.current_image.save(str(path), 'PNG'):
            raise OSError('无法写入截图，请检查目标目录与权限')
        if self.store is not None and self.task_id is not None:
            try:
                self.store.add_screenshot(self.task_id, self.issue_ordinal, path,
                                          self.current_frame.index, self.current_frame.timestamp)
            except StorageError as exc:
                raise StorageError(f'截图文件已保存，但历史关联失败：{exc}') from exc

    def save_dialog(self):
        self.pause()
        if self.current_frame is None or self.busy:
            return
        name = f'{self.issue.issue_type}_{self.current_frame.index:08d}.png'
        path, _ = QFileDialog.getSaveFileName(self, '保存当前截图', name, 'PNG 图片 (*.png)')
        if path:
            if not path.lower().endswith('.png'):
                path += '.png'
            try:
                self.save_image(path)
                suffix = '（已关联历史任务）' if self.task_id else '（当前结果未入库，无历史关联）'
                self.status.setText(f'截图已保存：{path}{suffix}')
            except (ValueError, OSError, StorageError) as exc:
                self.status.setText(str(exc))

    def reject(self):
        # Escape 也必须等解码线程退出，不能直接销毁 QThread。
        if self.worker.isRunning():
            self.closing = True
            self.pause()
            self.worker.stop()
        else:
            super().reject()

    def closeEvent(self, event):
        self.pause()
        if self.worker.isRunning():
            self.closing = True
            self.worker.stop()
            self.status.setText('正在关闭，等待当前帧读取完成…')
            event.ignore()
        else:
            super().closeEvent(event)

    @Slot()
    def worker_finished(self):
        if self.closing:
            self.close()
