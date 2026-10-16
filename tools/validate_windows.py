"""隔离 PATH 验证分发包；不等同于干净 Windows 虚拟机验收。"""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('package','video','output'):
        parser.add_argument('--'+flag,required=True)
    args = parser.parse_args()
    package, video, output = (Path(value).resolve() for value in (args.package,args.video,args.output))
    output.mkdir(parents=True,exist_ok=True)
    env = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','SQA_FFPROBE','QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH')}
    env['PATH'] = str(Path(env.get('WINDIR','C:/Windows'))/'System32')
    env['PYTHONIOENCODING'] = 'utf-8'
    cli = package/'ScreenQualityAnalyzer-CLI.exe'
    assert (package/'tools'/'ffprobe.exe').is_file(), '分发包缺少内置 FFprobe'
    # 显式无效覆盖应报错，而不是偷偷使用系统或内置版本。
    env['SQA_FFPROBE'] = str(output/'missing-ffprobe.exe')
    missing = subprocess.run([str(cli),str(video),'--json'],cwd=output,env=env,capture_output=True,timeout=60)
    assert missing.returncode == 1, '缺少 FFprobe 应明确失败'
    assert b'FFprobe' in missing.stderr
    del env['SQA_FFPROBE']
    command = [str(cli),str(video),'--json','--database',str(output/'cli.sqlite3'),'--report',str(output/'cli.xlsx'),'--overwrite-report']
    completed = subprocess.run(command,cwd=output,env=env,capture_output=True,timeout=120)
    assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    data = json.loads(completed.stdout.decode('utf-8'))
    assert data['statistics'] == {'black_count':2,'freeze_count':2,'total_count':4}
    assert data['quality']['score'] == 90.83
    (output/'cli.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    gui = subprocess.run([str(package/'ScreenQualityAnalyzer.exe'),'--self-test','--video',str(video),'--output',str(output/'gui')],cwd=output,env=env,timeout=150)
    assert gui.returncode == 0
    result = json.loads((output/'gui'/'result.json').read_text(encoding='utf-8'))
    assert result['ok'] and result['score'] == 90.83
    print(json.dumps({'cli':'passed','gui':result,'missing_ffprobe':'passed','isolated_path':env['PATH']},ensure_ascii=False))


if __name__ == '__main__':
    main()
