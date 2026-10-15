"""CFR 视频按帧定位，用于异常截图和静音画面复核。"""
import math
from pathlib import Path
import cv2
from core.models import VideoFrame
from core.video_reader import VideoReadError


class FrameExtractor:
    def __init__(self, path, fps, frame_count):
        if not math.isfinite(fps) or fps <= 0 or frame_count <= 0:
            raise ValueError('无效帧率或帧数')
        self.path = str(Path(path))
        self.fps = fps
        self.frame_count = frame_count
        self.capture = None

    def read(self, index):
        if not isinstance(index, int) or not 0 <= index < self.frame_count:
            raise ValueError('目标帧超出视频范围')
        if self.capture is None:
            self.capture = cv2.VideoCapture(self.path)
        try:
            if not self.capture.isOpened():
                raise VideoReadError('无法打开复核视频，文件可能已移动或删除')
            position = self.capture.get(cv2.CAP_PROP_POS_FRAMES)
            if round(position) != index:
                if not self.capture.set(cv2.CAP_PROP_POS_FRAMES, index):
                    raise VideoReadError('视频定位失败')
            ok, image = self.capture.read()
            if not ok:
                raise VideoReadError('无法解码目标帧')
            actual = self.capture.get(cv2.CAP_PROP_POS_FRAMES) - 1
            if not math.isfinite(actual) or abs(actual - index) > .5:
                raise VideoReadError('解码器未返回请求的目标帧')
            return VideoFrame(index, index / self.fps, image)
        except cv2.error as exc:
            raise VideoReadError(f'视频读取失败：{exc}') from exc

    def close(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None
