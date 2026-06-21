---
name: media-processing
description: 音视频处理工作流 — yt-dlp 下载 + whisper 转录 + edge-tts 语音合成 + FFmpeg 格式转换 + pydub 音频编辑
---

# 媒体处理工作流

## 工具速查

| 工具 | 安装状态 | 调用方式 |
|------|---------|---------|
| **yt-dlp** | ✅ pip 包 | `yt-dlp [URL] [参数]` |
| **whisper (faster-whisper)** | ✅ pip 包 | `python -c "from faster_whisper_utils import transcribe; transcribe('音频', 'base')"` |
| **edge-tts** | ✅ pip 包 (v7.2) | `edge-tts --voice zh-CN-XiaoxiaoNeural --text "..." --write-media out.mp3` |
| **FFmpeg** | ❌ 未安装（需 winget） | — |
| **pydub** | ✅ pip 包 | `python -c "from pydub import AudioSegment; ..."` |

> FFmpeg 未安装 — 大部分操作可用 `pydub` 或 Python 库替代。如需 FFmpeg：`winget install FFmpeg`

---

## 工作流

### 1. 📥 下载音视频（yt-dlp）

```bash
# 下载音频为 mp3（最佳质量）
yt-dlp -x --audio-format mp3 --audio-quality 0 "URL"

# 下载视频为 mp4
yt-dlp -f "bestvideo+bestaudio" --merge-output-format mp4 "URL"

# 下载播放列表指定范围
yt-dlp -x --audio-format mp3 --playlist-start 1 --playlist-end 5 "URL"
```

### 2. 📝 语音转文字（faster-whisper）

```bash
# 基础转录（自动检测语言）
python scripts/lib/whisper_local.py transcribe "audio.mp3"

# 中文优化（medium 模型平衡速度与精度）
python scripts/lib/whisper_local.py transcribe "audio.mp3" --model medium --language zh

# 指定输出目录
python scripts/lib/whisper_local.py transcribe "audio.mp3" --model base --output-dir ./transcripts/

# 输出 SRT 字幕
python scripts/lib/whisper_local.py transcribe "audio.mp3" --format srt
```

### 3. 🗣️ 文字转语音（edge-tts）

```bash
# 中文女声
edge-tts --voice zh-CN-XiaoxiaoNeural --text "你好，世界" --write-media output.mp3

# 日语男声
edge-tts --voice ja-JP-KeitaNeural --text "こんにちは" --write-media output.mp3

# 带 SSML 标签（更自然的语气）
edge-tts --voice zh-CN-XiaoxiaoNeural --ssml '<speak><prosody rate="-15%" pitch="+5%">你好，欢迎收听</prosody></speak>' --write-media output.mp3

# 从文件读取文本
edge-tts --voice zh-CN-XiaoxiaoNeural -f script.txt --write-media output.mp3
```

### 4. ✂️ 音频编辑（pydub）

```python
# 合并两个音频
python -c "
from pydub import AudioSegment
a = AudioSegment.from_file('part1.mp3')
b = AudioSegment.from_file('part2.mp3')
combined = a + b
combined.export('merged.mp3', format='mp3')
"

# 截取片段（毫秒）
python -c "
from pydub import AudioSegment
audio = AudioSegment.from_file('long.mp3')
clip = audio[30000:90000]  # 30s ~ 90s
clip.export('clip.mp3', format='mp3')
"

# 调整音量
python -c "
from pydub import AudioSegment
audio = AudioSegment.from_file('quiet.mp3')
louder = audio + 6  # +6dB
louder.export('louder.mp3', format='mp3')
"
```

### 5. 🔄 格式互转（pydub，无需 FFmpeg）

```bash
# mp3 → wav
python -c "from pydub import AudioSegment; AudioSegment.from_file('in.mp3').export('out.wav', format='wav')"

# wav → mp3
python -c "from pydub import AudioSegment; AudioSegment.from_file('in.wav').export('out.mp3', format='mp3')"

# m4a → mp3
python -c "from pydub import AudioSegment; AudioSegment.from_file('in.m4a').export('out.mp3', format='mp3')"
```

---

## 组合管道示例

### 视频下载 → 提取音频 → 转文字 → 翻译总结

```bash
# Step 1: 下载音频
yt-dlp -x --audio-format wav "https://youtu.be/xxx" -o "source.%(ext)s"

# Step 2: faster-whisper 转文字（支持更大文件，CPU 运行）
python scripts/lib/whisper_local.py transcribe "source.wav" --model medium --language en

# Step 3: 交给 AI 翻译/总结
# (在对话中处理 source.txt 即可)
```

### 文本 → 语音 → 裁剪 → 合并

```python
# 用 Python 脚本串联
python -c "
import subprocess, os
from pydub import AudioSegment

texts = ['开场白内容', '正文内容', '结束语内容']
segments = []

for i, t in enumerate(texts):
    out = f'seg_{i}.mp3'
    subprocess.run(['edge-tts', '--voice', 'zh-CN-XiaoxiaoNeural',
                    '--text', t, '--write-media', out], check=True)
    segments.append(AudioSegment.from_file(out))

final = sum(segments)
final.export('final.mp3', format='mp3')
print('Done: final.mp3')
"
```

---

## 源路径

- yt-dlp 下载默认目录：当前工作目录
- 建议输出：`D:/tmp/sandbox/`
- 转录缓存：whisper 默认不缓存，每次重新推理；输出 .txt/.srt 文件后可二次使用
