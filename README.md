# 智能会议设备投屏质量分析系统 V1.0

面向会议设备投屏测试，对录制的视频进行参数解析、黑屏及疑似冻结分析，逐步形成可复核的异常记录与测试报告。

## 当前阶段
处于技术验证阶段 V0.1；本次整理 M1 视频解析和 M2 黑屏检测。V1.0 是目标发布版本，尚未完成 GUI、数据库和报告。

## 技术栈
Python 3.11+、FFmpeg/FFprobe、OpenCV、NumPy、pytest。
后续计划使用 PySide6、SQLite/SQLAlchemy、openpyxl，尚未加入当前依赖。

## 里程碑
|阶段|目标|状态|
|---|---|---|
|M1|视频时长、分辨率、帧率、编码、码率、帧数及音频参数解析|本批实现|
|M2|逐帧读取、黑屏状态机、持续时间与严重等级|本批实现|
|M3|帧差法疑似冻结检测，保留静态 PPT 的人工复核|待开发|
|M4|统一分析引擎，汇总异常、进度及结果|待开发|

M4 之后逐步增加桌面界面、后台线程、项目/任务管理、SQLite 持久化、人工复核、质量评分、Excel 报告和打包发布。

## 快速开始
在项目目录执行：
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
ffprobe -version
ffmpeg -version
.venv\Scripts\python main.py "samples/test.mp4"
.venv\Scripts\python black_test.py "samples/black_2s.mp4"
.venv\Scripts\python -m pytest
```
FFmpeg/FFprobe 为独立系统依赖，请安装并加入 PATH。样本视频需自行放入 samples，或按该目录说明生成；不上传真实会议视频。

## 目录
- core：视频数据模型、参数解析、帧读取、检测算法。
- utils：FFprobe 调用和时间格式转换。
- exceptions：统一视频处理异常。
- tests：单元测试及自动生成素材的集成测试。
- samples：本地测试视频及生成说明（视频不纳入 Git）。
- docs：开发说明、验证记录及后续软著材料。

## 当前边界
- 黑屏依据平均灰度小于 10 且持续至少 0.5 秒判定；低于 1 秒 LOW、1 至不足 2 秒 MEDIUM、至少 2 秒 HIGH。阈值可配置。
- 逐帧时间按 index / fps 计算，仅针对固定帧率素材；变帧率 PTS 支持留待后续。
- 缺失帧数时按时长乘帧率估算；容器码率回退值包含音频等开销，不等同于精确视频流码率。
- 黑屏结果需要结合实际画面用途复核；本阶段不测量实时投屏端到端延迟。

## 软著用途
本仓库用于持续保存实际开发的源代码、版本记录、测试证据及后续说明书，作为“智能会议设备投屏质量分析系统 V1.0”的研发材料基础。后续材料应与最终发布版本、软件名称及实际功能一致。当前仓库初始化和技术验证代码不代表已经完成 V1.0 或取得登记。

