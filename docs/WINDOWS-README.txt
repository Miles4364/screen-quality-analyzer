投屏质量分析 V0.9 Windows x64 便携版

1. 解压整个文件夹，保留 _internal。双击 ScreenQualityAnalyzer.exe。
2. 本包不附带 FFprobe。安装 FFmpeg 后将其加入 PATH，或把自己安装的
   ffprobe.exe 放到程序旁 tools 文件夹，或设置 SQA_FFPROBE 为其完整路径。
   动态构建的 FFprobe 还需配齐对应 DLL。分析只需 FFprobe，样本生成才需要 ffmpeg。
3. 默认数据库：%LOCALAPPDATA%\ScreenQualityAnalyzer\analysis.sqlite3。
   如需继续源码版历史，关闭程序后备份并复制旧数据库至此，或启动时传入
   --database "旧数据库完整路径"。源视频和截图不会自动复制。
4. 使用流程：选择视频→分析→选择异常查看画面→记录人工复核→导出 Excel。
5. 命令行入口：
   ScreenQualityAnalyzer-CLI.exe "视频.mp4" --json
   ScreenQualityAnalyzer-CLI.exe "视频.mp4" --report "报告.xlsx"
6. 备份：退出程序后备份数据库、原视频与截图。升级到结构版本 3 后，旧版
   V0.7 及更早软件无法读取；回退须使用升级前备份。V0.8 到 V0.9 不改变结构。
7. 不要只复制 exe，必须保留整个文件夹。此版本没有安装器、自动更新或代码签名。
   正式发布前仍需在独立、无开发环境的 Windows 电脑验收。
8. 辅助评分与疑似冻结需人工判断，不代表设备合格结论；仅保证 CFR 定位。

第三方组件版本和许可证见 build-versions.json 与 licenses 文件夹。
FFprobe 未随包分发，用户需自行取得并遵循相应发行版许可。
