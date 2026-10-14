# 智能会议设备投屏质量分析系统 V1.0

面向会议设备投屏测试，对录制的视频进行参数解析、黑屏及疑似冻结分析。当前为技术验证版 V0.1，V1.0 是后续目标版本。

## 当前进度

|里程碑|能力|状态|
|---|---|---|
|M1|视频 Metadata、视频/音频编码与参数解析|完成|
|M2|VideoReader、黑屏检测、末尾事件与读取异常处理|完成|
|M3|帧差疑似冻结检测、阈值配置、单元测试|完成|
|M4|统一 AnalysisEngine、单视频 CLI、JSON 结果、混合样本验证|完成核心闭环|

## 安装和运行

要求 Python 3.11+，另行安装 FFmpeg/FFprobe 并加入 PATH。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
.venv\Scripts\python main.py "samples/test.mp4"
.venv\Scripts\python main.py "samples/test.mp4" --json
.venv\Scripts\python main.py "samples/test.mp4" --black-threshold 10 --black-duration 0.5 --freeze-pixel-threshold 5 --freeze-change-ratio 0.01 --freeze-duration 0.5
.venv\Scripts\python black_test.py "samples/test.mp4"
```

CLI 输出 Metadata、BlackScreen/Freeze 数量、按时间排序的事件、处理帧数、耗时及分析速度。`--json` 输出 `video_metadata`、`issues`、`statistics`、`processing_time`、`processed_frames` 和 `analyzed_duration`。退出码 0 表示分析成功（即使检测到异常），1 表示分析失败，2 表示命令行参数错误。错误写入 stderr。

程序接口：

```python
from core.analysis_engine import AnalysisEngine
from core.models import AnalysisConfig

result = AnalysisEngine(AnalysisConfig(freeze_duration=1.0)).analyze("samples/test.mp4")
print(result.statistics)
```

每次分析创建独立检测器，引擎可重复使用；视频逐帧处理，不将整个视频载入内存。使用 `with VideoReader(...)` 可保证异常或提前退出时释放文件。读取帧数低于 OpenCV 报告帧数时按提前结束报错。

## 测试与可复现样本

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python tools/generate_samples.py
.venv\Scripts\python main.py samples/final_validation.mp4
.venv\Scripts\python tools/generate_samples.py "samples/最终验收 1080p.mp4" --width 1920 --height 1080
.venv\Scripts\python main.py "samples/最终验收 1080p.mp4"
```

2026-10-14：61 项 pytest 测试全部通过，无跳过。测试包括真实 MP4 编码/解码、720p/1080p、30/29.97 FPS、中文路径、无效文件、0.5 秒边界、视频末尾、多段事件、JSON CLI 和引擎重复使用。缺少 FFmpeg/FFprobe 时部分集成测试会跳过；跳过不代表通过验收。

生成器创建 60 秒、30 FPS 的动态测试图，插入黑屏 10–12 秒及 40–41 秒、冻结 25–27 秒及 50–53 秒，预期仅 4 个事件。视频留在本地，Git 保存生成器和验证记录。测试使用人工合成但经过实际编码的视频，并非真实会议录屏；真实设备素材的泛化验证仍待补充。

## 判定规则与已知边界

- 黑屏：缩放至 320×180，平均灰度严格小于 10，持续至少 0.5 秒。
- 冻结：相邻缩放灰度帧绝对差大于 5 的像素比例严格小于 1%，持续至少 0.5 秒。事件从第一张重复画面开始；黑屏候选切断冻结候选，避免重复告警。
- 严重等级：不足 1 秒 LOW，1 至不足 2 秒 MEDIUM，至少 2 秒 HIGH。
- 事件使用 `[start_time, end_time)`；视频末尾结束时间包含最后一帧的显示时长。
- 时间按 `index / fps` 计算，只保证固定帧率（CFR）素材；变帧率 PTS 尚未支持。OpenCV 不能可靠区分所有损坏视频与 EOF；未知帧数时无法保证识别提前截断，错误帧数也可能导致保守报错。
- 静态 PPT、低运动画面可能被标为疑似冻结；低亮度内容也可能触发黑屏。结果需人工复核，不代表已确认设备故障。
- 缺失 Metadata 帧数时使用时长×帧率估算；容器时长可能含较长音轨，因此事件末尾使用实际解码帧数计算。容器码率回退值包含音频等开销。
- 本版不测量端到端投屏延迟，未承诺真实会议数据上的准确率。

## 目录与后续里程碑

`core/` 保存模型、解析器、读取器、检测器及分析引擎；`tests/` 保存单元/集成测试；`tools/` 保存样本生成器；`samples/` 保存本地样本；`docs/` 保存开发与验证记录。

后续按顺序推进：V0.2 PySide6 最小 GUI、后台分析及进度/取消；V0.3 异常截图与视频跳转；V0.4 SQLite；V0.5 项目/任务管理；V0.6 Excel 报告；V0.7 质量评分；V0.8 人工复核；V0.9 打包和回归；V1.0 发布及软著材料整理。算法方面补充真实会议素材、VFR 时间戳支持及静态内容误报评估。

## 软著用途

保存真实开发代码、版本记录和测试证据，后续说明书与最终发布的软件功能保持一致。当前技术验证版不代表 V1.0 已发布或已取得登记。
