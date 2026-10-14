# 测试素材

视频仅存本地，不纳入 Git。自动化集成测试会在临时目录生成素材。

可在项目根目录生成 10 秒、3～5 秒为黑屏的固定帧率样本：
```powershell
ffmpeg -f lavfi -i "testsrc2=size=320x180:rate=30:duration=10" -vf "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,3,4.999)'" -c:v mpeg4 -y samples/black_2s.mp4
```

