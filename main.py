"""单个视频分析命令行入口。"""
import argparse
import json
import sys
from dataclasses import asdict
from core.analysis_engine import AnalysisEngine
from core.models import AnalysisConfig
from exceptions.video_exception import VideoError
from utils.time_util import seconds_to_time
from storage.analysis_store import AnalysisStore, StorageError


def main(argv=None):
    parser = argparse.ArgumentParser(description='投屏质量分析：Metadata、BlackScreen、Freeze')
    parser.add_argument('video_path', help='待分析的视频路径')
    parser.add_argument('--database', help='可选：保存结果到指定 SQLite 数据库')
    parser.add_argument('--task-name', help='保存任务的自定义名称')
    parser.add_argument('--project-id', help='已存在项目的 ID；不传则未分组')
    parser.add_argument('--report', help='导出 Excel 报告到 .xlsx 文件')
    parser.add_argument('--overwrite-report', action='store_true', help='允许覆盖已有报告')
    parser.add_argument('--json', action='store_true', help='输出可机器读取的 JSON')
    for name, default in asdict(AnalysisConfig()).items():
        parser.add_argument('--' + name.replace('_', '-'), type=float, default=default)
    args = parser.parse_args(argv)
    if (args.task_name or args.project_id) and not args.database:
        parser.error('--task-name 和 --project-id 需要 --database')
    if args.overwrite_report and not args.report:
        parser.error('--overwrite-report 需要 --report')
    config = AnalysisConfig(**{name: getattr(args, name) for name in asdict(AnalysisConfig())})
    try:
        result = AnalysisEngine(config).analyze(args.video_path)
    except (VideoError, ValueError) as exc:
        print(f'分析失败：{exc}', file=sys.stderr)
        return 1
    task_id = None
    if args.database:
        try:
            task_id = AnalysisStore(args.database).save_result(result, config, title=args.task_name, project_id=args.project_id)
        except StorageError as exc:
            print(f'分析完成，但结果保存失败：{exc}', file=sys.stderr)
            return 1
    report_path = None
    if args.report:
        from reporting.excel_report import export_report, ReportError
        try:
            task = AnalysisStore(args.database).load_task(task_id) if task_id else None
            report_path = export_report(result, args.report, config=config, task=task,
                                        overwrite=args.overwrite_report,
                                        protected_paths=[args.database] if args.database else [])
        except (ReportError, StorageError, OSError) as exc:
            print(f'分析完成，但报告导出失败：{exc}', file=sys.stderr)
            return 1
    if args.json:
        data = asdict(result)
        data['statistics'] = result.statistics
        data['quality'] = asdict(result.quality)
        if task_id is not None:
            data['task_id'] = task_id
        if report_path is not None:
            data['report_path'] = str(report_path)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if report_path:
        print(f'报告：{report_path}')
    if task_id:
        print(f'历史任务：{task_id}')
    m = result.video_metadata
    print('智能会议设备投屏质量分析系统 技术验证版 V0.9.1')
    q = result.quality
    print(f'辅助质量评分：{q.score if q.score is not None else "不可用"} / 100 | 规则：{q.rule_version}')
    print(f'黑屏扣分：{q.black_penalty:.2f} | 疑似冻结扣分：{q.freeze_penalty:.2f} | {q.reason or "项目自定义指标，需人工复核"}')
    print(f'Metadata：{m.filename} | {m.resolution} | {m.fps:.3f} FPS')
    print(f'时长：{seconds_to_time(m.duration)} | 编码：{m.codec} | 码率：{m.bitrate_mbps:.2f} Mbps')
    print(f'音频：{m.audio_codec or "无"} | 采样率：{m.sample_rate or 0} Hz')
    print(f'BlackScreen：{result.statistics["black_count"]} | Freeze：{result.statistics["freeze_count"]}')
    for index, issue in enumerate(result.issues, 1):
        print(f'#{index:03d} {issue.issue_type} {seconds_to_time(issue.start_time)} → '
              f'{seconds_to_time(issue.end_time)} | {issue.duration:.3f}s | {issue.severity}')
    speed = result.analyzed_duration / result.processing_time if result.processing_time else 0
    print(f'处理帧数：{result.processed_frames}/{m.frame_count} | 耗时：{result.processing_time:.3f}s | 速度：{speed:.2f}x')
    return 0


if __name__ == '__main__':
    sys.exit(main())
