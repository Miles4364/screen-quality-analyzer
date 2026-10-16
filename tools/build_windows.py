"""在 Windows 上构建两个入口、收集许可证并生成分发 ZIP 与校验值。"""
import hashlib
import argparse
import os
from importlib import metadata
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != 'win32':
        raise SystemExit('Windows 分发包必须在 Windows 上构建')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg-dir', required=True, help='包含 bin/ffprobe.exe、LICENSE 和 README.txt 的静态发行目录')
    args = parser.parse_args()
    ffmpeg = Path(args.ffmpeg_dir).resolve()
    for relative in ('bin/ffprobe.exe', 'LICENSE', 'README.txt'):
        if not (ffmpeg/relative).is_file():
            raise SystemExit(f'缺少分发文件：{ffmpeg/relative}')
    # 防止 PATH 中其他应用的同名 DLL 被打包（例如 Poppler 的 ICU）。
    env = os.environ.copy()
    env['PATH'] = str(Path(env.get('WINDIR','C:/Windows'))/'System32')
    probe = subprocess.run([str(ffmpeg/'bin/ffprobe.exe'),'-version'],env=env,capture_output=True,text=True,encoding='utf-8',check=True,timeout=30)
    if '--enable-static' not in probe.stdout or '--enable-nonfree' in probe.stdout:
        raise SystemExit('请提供可分发的静态 FFprobe 构建（不接受 nonfree）')
    subprocess.run([sys.executable,'-m','PyInstaller','--clean','--noconfirm',str(ROOT/'ScreenQualityAnalyzer.spec')],cwd=ROOT,env=env,check=True)
    package = ROOT/'dist'/'ScreenQualityAnalyzer'
    shutil.copy2(ROOT/'docs'/'WINDOWS-README.txt',package/'使用说明.txt')
    notices = package/'licenses'
    notices.mkdir(exist_ok=True)
    (package/'tools').mkdir(exist_ok=True)
    shutil.copy2(ffmpeg/'bin/ffprobe.exe', package/'tools'/'ffprobe.exe')
    ffnotice = notices/'FFprobe'
    ffnotice.mkdir(exist_ok=True)
    for name in ('LICENSE','README.txt'):
        shutil.copy2(ffmpeg/name,ffnotice/name)
    (ffnotice/'version.txt').write_text(probe.stdout,encoding='utf-8')
    with (package/'tools'/'ffprobe.exe').open('rb') as stream:
        probe_hash = hashlib.file_digest(stream,'sha256').hexdigest()
    (ffnotice/'ffprobe.sha256').write_text(probe_hash+'  ffprobe.exe\n',encoding='ascii')
    names = ['PySide6','PySide6_Addons','PySide6_Essentials','shiboken6','numpy','opencv-python','openpyxl','et_xmlfile','pyinstaller']
    versions = {}
    versions['FFprobe'] = {'version':probe.stdout.splitlines()[0], 'sha256':probe_hash}
    for name in names:
        dist = metadata.distribution(name)
        versions[name] = dist.version
        target = notices/name
        target.mkdir(exist_ok=True)
        (target/'METADATA.txt').write_text(dist.read_text('METADATA') or '',encoding='utf-8')
        for file in dist.files or []:
            if any(token in file.name.lower() for token in ('license','copying','copyright','notice')) and '.dist-info/' in str(file).replace('\\','/'):
                destination = target/str(file).replace('\\','/').split('.dist-info/',1)[1]
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(dist.locate_file(file),destination)
    import json
    (package/'build-versions.json').write_text(json.dumps(versions,indent=2),encoding='utf-8')
    archive = Path(shutil.make_archive(str(ROOT/'dist'/'ScreenQualityAnalyzer-V0.9.1-Windows-x64'),'zip',ROOT/'dist','ScreenQualityAnalyzer'))
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream,'sha256').hexdigest()
    archive.with_suffix('.sha256').write_text(f'{digest}  {archive.name}\n',encoding='ascii')
    print(f'Built: {archive}\nSHA256: {digest}')


if __name__ == '__main__':
    main()
