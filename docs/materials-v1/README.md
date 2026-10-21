# V1.0 材料生成与范围

本轮按提供的规范整理，用户已确认保留 PySide6。三栏布局、真实统计图、软件名称和版本已统一。详细偏离与适用边界见 specification_notes.txt，算法核对见 algorithm_notes.txt，9 条官方参考文献见 references.json。

交付内容：软件使用说明书 DOCX/PDF、源程序鉴别材料 DOCX/PDF、软件信息 TXT、完整项目源码 ZIP、逐文件 MD5/SHA-256 与行号映射 source_manifest.json、真实界面截图及采集记录。

## 重建顺序

1. 安装项目运行依赖，生成标准 60 秒合成验证视频。
2. 在可见 Windows 桌面运行 `python gui_main.py "samples/最终验收 1080p.mp4" --auto-screenshot`，核对 capture.json 为成功并查看每张截图。
3. 在含 python-docx 与 Pillow 的文档环境运行 `python tools/export_source_document.py --output-dir "输出目录" --source-zip`。`--plan-only` 只统计，不创建文档。
4. 运行 `python tools/build_materials.py --output-dir "输出目录"`，生成说明书、信息表与流程图。
5. 使用 Word 或可用的文档渲染器转换 PDF，核对实际页数、源程序行数、截图和页眉页脚，再登记渲染结果。修改运行源码后必须重建源程序清单与所有引用该清单的材料。

## 统计口径

运行程序量包含入口、core、gui、storage、reporting、utils、exceptions，以及入口引用的运行辅助模块；测试、构建工具、第三方代码不计入。完整项目 ZIP 另外包含测试、工具、配置与文本说明，排除视频、图片、数据库、个人历史、虚拟环境和构建产物。

源程序材料是阅读排版投影：移除可安全识别的注释、独立文档字符串及非字符串空行，长行软换行；原始源码保持原字节。哈希对应原始源码，映射对应每一排版行的原文件行。超过 60 页时取连续前 30 页和连续后 30 页，保留全量编号。

保留数据类、自定义异常、参数化 SQL 和必要注释，不加入无关业务、虚构用户记录、无来源争议或为凑行数重复代码。项目使用 AI 辅助开发；格式和哈希不证明人工独立编写。权利人、权利归属、完成日期和发表情况需要申请人如实核对，技术信息表不代替这些声明。
