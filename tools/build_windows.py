"""在 Windows 上构建两个入口、收集许可证并生成分发 ZIP 与校验值。"""
import hashlib
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
    # 防止 PATH 中其他应用的同名 DLL 被打包（例如 Poppler 的 ICU）。
    env = os.environ.copy()
    env['PATH'] = str(Path(env.get('WINDIR','C:/Windows'))/'System32')
    subprocess.run([sys.executable,'-m','PyInstaller','--clean','--noconfirm',str(ROOT/'ScreenQualityAnalyzer.spec')],cwd=ROOT,env=env,check=True)
    package = ROOT/'dist'/'ScreenQualityAnalyzer'
    shutil.copy2(ROOT/'docs'/'WINDOWS-README.txt',package/'使用说明.txt')
    notices = package/'licenses'
    notices.mkdir(exist_ok=True)
    names = ['PySide6','PySide6_Addons','PySide6_Essentials','shiboken6','numpy','opencv-python','openpyxl','et_xmlfile','pyinstaller']
    versions = {}
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
    archive = Path(shutil.make_archive(str(ROOT/'dist'/'ScreenQualityAnalyzer-V0.9-Windows-x64'),'zip',ROOT/'dist','ScreenQualityAnalyzer'))
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream,'sha256').hexdigest()
    archive.with_suffix('.sha256').write_text(f'{digest}  {archive.name}\n',encoding='ascii')
    print(f'Built: {archive}\nSHA256: {digest}')


if __name__ == '__main__':
    main()
