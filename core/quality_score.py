"""项目自定义的时长占比评分，不代表行业认证或人工复核结论。"""
from dataclasses import dataclass
import math

RULE_VERSION = 'duration-v1'
RULE_DESCRIPTION = '100 × (1 − (黑屏秒数 + 0.5 × 非黑屏疑似冻结秒数) / 实际分析秒数)；同类取并集，重叠优先黑屏。'


@dataclass(frozen=True)
class QualityScore:
    rule_version: str = RULE_VERSION
    score: float | None = None
    analyzed_seconds: float = 0.0
    black_seconds: float = 0.0
    freeze_seconds: float = 0.0
    black_penalty: float = 0.0
    freeze_penalty: float = 0.0
    reason: str = ''


def _union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def calculate_quality(result):
    duration = result.analyzed_duration
    if not math.isfinite(duration) or duration <= 0 or result.processed_frames <= 0:
        return QualityScore(reason='无有效分析时长或帧数，无法评分')
    intervals = {'BLACK_SCREEN': [], 'FREEZE': []}
    for issue in result.issues:
        if issue.issue_type not in intervals:
            return QualityScore(reason='包含不支持的异常类型，无法评分')
        start, end = issue.start_time, issue.end_time
        if not math.isfinite(start) or not math.isfinite(end) or end < start:
            return QualityScore(reason='异常时间无效，无法评分')
        start, end = max(0.0, start), min(duration, end)
        if end > start:
            intervals[issue.issue_type].append((start, end))
    black = _union(intervals['BLACK_SCREEN'])
    freeze = _union(intervals['FREEZE'])
    black_seconds = sum(b-a for a, b in black)
    # 两个有序、不重叠的区间列表，线性计算交集。
    overlap = 0.0
    i = j = 0
    while i < len(black) and j < len(freeze):
        a, b = black[i]
        c, d = freeze[j]
        overlap += max(0.0, min(b, d) - max(a, c))
        if b <= d:
            i += 1
        else:
            j += 1
    freeze_seconds = max(0.0, sum(b-a for a, b in freeze) - overlap)
    bp = 100 * black_seconds / duration
    fp = 50 * freeze_seconds / duration
    return QualityScore(score=round(max(0.0, min(100.0, 100-bp-fp)), 2),
                        analyzed_seconds=duration, black_seconds=black_seconds,
                        freeze_seconds=freeze_seconds, black_penalty=bp, freeze_penalty=fp)
