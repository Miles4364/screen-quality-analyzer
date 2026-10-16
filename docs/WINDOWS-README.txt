投屏质量分析 V0.9.2 Windows x64 便携版

1. 解压整个文件夹，保留 _internal。双击 ScreenQualityAnalyzer.exe。
2. 已内置 tools/ffprobe.exe，正常使用无需安装 FFmpeg 或设置环境变量。
   保留 tools 文件夹。若设置了 SQA_FFPROBE，该指定路径优先；无效时可清除变量
   后使用内置版本。内置版本为 5.1.2-essentials_build-www.gyan.dev。
3. 默认数据库：%LOCALAPPDATA%\ScreenQualityAnalyzer\analysis.sqlite3。
   如需继续源码版历史，关闭程序后备份并复制旧数据库至此，或启动时传入
   --database "旧数据库完整路径"。源视频和截图不会自动复制。
4. 使用流程：选择视频→分析→选择异常查看画面→记录人工复核→导出 Excel。
5. 命令行入口：
   ScreenQualityAnalyzer-CLI.exe "视频.mp4" --json
   ScreenQualityAnalyzer-CLI.exe "视频.mp4" --report "报告.xlsx"
6. 备份：退出程序后备份数据库、原视频与截图。升级到结构版本 3 后，旧版
   V0.7 及更早软件无法读取；回退须使用升级前备份。V0.8 到 V0.9.2 不改变结构。
7. 不要只复制 exe，必须保留整个文件夹。此版本没有安装器、自动更新或代码签名。
   正式发布前仍需在独立、无开发环境的 Windows 电脑验收。
8. 辅助评分与疑似冻结需人工判断，不代表设备合格结论；仅保证 CFR 定位。

第三方组件版本和许可证见 build-versions.json 与 licenses 文件夹。
FFprobe 为独立 GPLv3 程序；原发行说明、源码地址、许可证及哈希见 licenses/FFprobe。
此包用于本地验收；对外正式分发前需完成对应源码及依赖源码提供方式的核对。
