# 可复现测试素材

在仓库根目录运行 `.venv\Scripts\python tools/generate_samples.py`，生成 `samples/final_validation.mp4`（60 秒 / 640×360 / 30 FPS / MPEG-4）。加 `--width 1920 --height 1080` 可生成 1080p 素材。

|片段|预期事件|
|---|---|
|10–12 秒|BLACK_SCREEN|
|25–27 秒|FREEZE|
|40–41 秒|BLACK_SCREEN|
|50–53 秒|FREEZE|

其他区间是持续运动的测试图。预期总数 4，无重复黑屏冻结事件。pytest 还在临时目录生成正常、短异常、阈值边界和 EOF 样本。样本是人工测试图经真实 MP4 编码，不是真实会议录屏。

视频不纳入 Git；生成脚本保存在 tools/generate_samples.py。真实设备录屏需要另外提供并人工标注，后续用于评估误报和漏报。
