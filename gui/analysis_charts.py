"""按当前分析结果绘图，不缓存视频帧，也不改变检测和评分数据。"""
from dataclasses import dataclass, field
import math

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget, QSizePolicy

from core.review import REVIEW_LABELS, review_counts


@dataclass
class ChartData:
    duration: float = 0.0
    events: list = field(default_factory=list)
    composition: list = field(default_factory=list)
    reviews: list = field(default_factory=list)
    available: bool = False
    reason: str = '完成分析或打开历史任务后显示统计图表。'


def prepare_chart_data(result, reviews=()):
    """时间轴使用截断到有效范围的区间；时长构成复用评分的去重结果。"""
    if result is None:
        return ChartData()
    quality = result.quality
    if quality.score is None:
        return ChartData(reason=f'统计不可用：{quality.reason}')
    events = []
    for ordinal, issue in enumerate(result.issues):
        start = max(0.0, issue.start_time)
        end = min(quality.analyzed_seconds, issue.end_time)
        if math.isfinite(start) and math.isfinite(end) and end > start:
            events.append((ordinal, issue.issue_type, start, end))
    counts = review_counts(len(result.issues), reviews)
    return ChartData(
        duration=quality.analyzed_seconds, events=events,
        composition=[
            ('黑屏', quality.black_seconds),
            ('非黑屏疑似冻结', quality.freeze_seconds),
            ('其余已分析时长', max(0.0, quality.analyzed_seconds -
                                     quality.black_seconds - quality.freeze_seconds)),
        ],
        reviews=[(REVIEW_LABELS[key], count) for key, count in counts.items()],
        available=True, reason='',
    )


class ChartCanvas(QWidget):
    COLORS = ('#166156', '#538f84', '#c6ddd7')
    TYPES = ('BLACK_SCREEN', 'FREEZE')
    LABELS = ('黑屏', '疑似冻结')

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.data = ChartData()
        self.setMinimumSize(400, 300)
        self.setAccessibleName(('异常时间轴', '事件持续时间散点图', '分析时长构成', '人工复核统计')[kind])

    def set_data(self, data):
        self.data = data
        self.update()

    @staticmethod
    def _text(painter, rect, text, alignment=Qt.AlignmentFlag.AlignCenter):
        painter.setPen(QColor('#24483f'))
        painter.drawText(rect, alignment, text)

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor('#ffffff'))
            if not self.data.available:
                self._text(painter, QRectF(self.rect()), self.data.reason)
                return
            area = QRectF(90, 40, max(240, self.width() - 125), max(190, self.height() - 110))
            if self.kind == 0:
                self._timeline(painter, area)
            elif self.kind == 1:
                self._scatter(painter, area)
            elif self.kind == 2:
                self._bars(painter, area, self.data.composition, self.data.duration, '秒')
            else:
                self._bars(painter, area, self.data.reviews,
                           max(1, sum(value for _, value in self.data.reviews)), '段')
        finally:
            painter.end()

    def _time_axis(self, painter, area, maximum):
        for tick in range(5):
            x = area.left() + area.width() * tick / 4
            painter.setPen(QPen(QColor('#d8e7e2'), 1))
            painter.drawLine(x, area.top(), x, area.bottom())
            self._text(painter, QRectF(x - 36, area.bottom() + 7, 72, 24),
                       f'{maximum * tick / 4:.1f}')
        self._text(painter, QRectF(area.left(), area.bottom() + 34, area.width(), 24), '视频时间（秒）')

    def _timeline(self, painter, area):
        self._time_axis(painter, area, self.data.duration)
        for lane, label in enumerate(self.LABELS):
            y = area.top() + area.height() * (lane + .5) / 2
            self._text(painter, QRectF(0, y - 14, 85, 28), label)
            painter.fillRect(QRectF(area.left(), y - 23, area.width(), 46), QColor('#eff5f2'))
            for _, kind, start, end in self.data.events:
                if kind == self.TYPES[lane]:
                    x = area.left() + area.width() * start / self.data.duration
                    width = max(2.0, area.width() * (end - start) / self.data.duration)
                    painter.fillRect(QRectF(x, y - 23, width, 46), QColor(self.COLORS[lane]))
        if not self.data.events:
            self._text(painter, QRectF(area.left(), area.top(), area.width(), 30), '本次分析未检出异常')

    def _scatter(self, painter, area):
        self._time_axis(painter, area, self.data.duration)
        maximum = max((end - start for _, _, start, end in self.data.events), default=1)
        maximum = max(1, maximum * 1.15)
        for tick in range(5):
            y = area.bottom() - area.height() * tick / 4
            painter.setPen(QPen(QColor('#e1ece7'), 1))
            painter.drawLine(area.left(), y, area.right(), y)
            self._text(painter, QRectF(0, y - 12, 80, 24), f'{maximum * tick / 4:.1f}')
        self._text(painter, QRectF(0, 4, 180, 28), '持续时间（秒）')
        for _, kind, start, end in self.data.events:
            x = area.left() + area.width() * start / self.data.duration
            y = area.bottom() - area.height() * (end - start) / maximum
            color = self.COLORS[self.TYPES.index(kind)]
            painter.setPen(QPen(QColor('#ffffff'), 1))
            painter.setBrush(QColor(color))
            painter.drawEllipse(QRectF(x - 5, y - 5, 10, 10))
        if not self.data.events:
            self._text(painter, area, '本次分析未检出异常')

    def _bars(self, painter, area, values, maximum, unit):
        # 标签采用两行，避免长中文名称挤压绘图区。
        height = area.height() / 3
        for index, (label, value) in enumerate(values):
            top = area.top() + index * height
            self._text(painter, QRectF(16, top, self.width() - 32, 28),
                       f'{label}    {value:.3f} 秒' if unit == '秒' else f'{label}    {value} 段',
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            bar = QRectF(16, top + 34, self.width() - 48, min(36, height - 42))
            painter.fillRect(bar, QColor('#eff5f2'))
            if value > 0:
                painter.fillRect(QRectF(bar.left(), bar.top(), bar.width() * value / maximum,
                                       bar.height()), QColor(self.COLORS[index]))


class AnalysisCharts(QWidget):
    TAB_NAMES = ('异常时间轴', '事件持续时间', '时长构成', '人工复核')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = ChartData()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel('当前任务统计')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        self.context_label = QLabel('尚未选择分析结果')
        self.context_label.setWordWrap(True)
        self.context_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.context_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.context_label)
        self.tabs = QTabWidget()
        self.canvases = []
        for index, name in enumerate(self.TAB_NAMES):
            canvas = ChartCanvas(index)
            self.canvases.append(canvas)
            self.tabs.addTab(canvas, name)
        layout.addWidget(self.tabs, 1)
        self.note = QLabel(
            '时间轴与散点图：深色为黑屏，浅色为疑似冻结。'
            '时长构成按区间并集统计，重叠优先归入黑屏；人工复核不会改变自动检测结果。'
        )
        self.note.setWordWrap(True)
        self.note.setObjectName('muted')
        layout.addWidget(self.note)

    def set_result(self, result, reviews=()):
        self.data = prepare_chart_data(result, reviews)
        self.context_label.setText(
            f'{result.video_metadata.filename}  ·  已分析 {result.analyzed_duration:.3f} 秒  ·  '
            f'{len(result.issues)} 个自动检测事件' if result is not None else '尚未选择分析结果'
        )
        for canvas in self.canvases:
            canvas.set_data(self.data)
