"""生成确定性的 CFR 动态测试图，编码为真实 MP4；不含真实会议内容。"""
import argparse
from pathlib import Path
import cv2
import numpy as np


def generate(path, duration=60, fps=30, size=(640, 360), black=((10, 12), (40, 41)), freeze=((25, 27), (50, 53))):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
    if not writer.isOpened():
        raise RuntimeError('无法创建 MP4 编码器')
    x = np.arange(size[0], dtype=np.int32)[None, :]
    y = np.arange(size[1], dtype=np.int32)[:, None]
    try:
        for index in range(round(duration * fps)):
            t = index / fps
            source_index = index
            for start, end in freeze:
                if start <= t < end:
                    source_index = round(start * fps)
            gray = ((x + y + source_index * 17) % 180 + 50).astype(np.uint8)
            image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            if any(start <= t < end for start, end in black):
                image[:] = 0
            writer.write(image)
    finally:
        writer.release()
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', default='samples/final_validation.mp4')
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int, default=360)
    args = parser.parse_args()
    generate(args.output, size=(args.width, args.height))
    print(f'已生成：{args.output}')
