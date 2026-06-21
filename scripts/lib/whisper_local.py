"""
本地语音转文字 — faster-whisper（CPU 推理，无需 GPU）

用法:
  python scripts/core/whisper_local.py transcribe <音频文件> [选项]

选项:
  --model       模型大小: tiny/base/small/medium/large-v3 (默认: base)
  --language    语言代码: zh/en/ja/... (默认: 自动检测)
  --format      输出格式: txt/srt (默认: txt)
  --output-dir  输出目录 (默认: 音频所在目录)
  --device      推理设备: cpu/auto (默认: cpu)

示例:
  python scripts/core/whisper_local.py transcribe voice.mp3
  python scripts/core/whisper_local.py transcribe voice.mp3 --model medium --language zh
  python scripts/core/whisper_local.py transcribe voice.mp3 --format srt --output-dir ./transcripts/
"""

import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("[错误] 需要安装 faster-whisper: pip install faster-whisper")
    sys.exit(1)


def transcribe_file(
    audio_path: str,
    model_size: str = "base",
    language: str | None = None,
    output_format: str = "txt",
    output_dir: str | None = None,
    device: str = "cpu",
) -> str:
    """转录音频文件，输出文本/字幕文件"""
    if not os.path.exists(audio_path):
        return f"[错误] 文件不存在: {audio_path}"

    # 计算 device & compute_type
    if device == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    compute = "int8" if device == "cpu" else "float16"

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"[whisper] 加载模型 {model_size} ({device}/{compute})...", flush=True)
    print(f"[whisper] 音频 {audio_path} ({size_mb:.1f}MB)", flush=True)

    try:
        model = WhisperModel(model_size, device=device, compute_type=compute)
    except Exception as e:
        return f"[错误] 模型加载失败: {e}"

    print(f"[whisper] 转写中...", flush=True)
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    detected_lang = info.language
    lang_prob = info.language_probability
    print(f"[whisper] 检测语言: {detected_lang} (p={lang_prob:.2f})", flush=True)

    # 收集所有片段
    all_segments = list(segments)
    if not all_segments:
        return "[警告] 未识别出任何文字"

    # 决定输出目录
    out_dir = output_dir or os.path.dirname(os.path.abspath(audio_path))
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    full_text = " ".join(seg.text.strip() for seg in all_segments)

    # 输出 txt
    txt_path = os.path.join(out_dir, f"{base_name}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"[whisper] TXT → {txt_path} ({len(full_text)} 字)", flush=True)

    # 输出 srt
    srt_path = os.path.join(out_dir, f"{base_name}.srt")
    srt_lines = []
    for i, seg in enumerate(all_segments, 1):
        start_s = _fmt_srt(seg.start)
        end_s = _fmt_srt(seg.end)
        srt_lines.append(f"{i}\n{start_s} --> {end_s}\n{seg.text.strip()}\n")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    print(f"[whisper] SRT → {srt_path} ({len(all_segments)} 条字幕)", flush=True)

    if output_format == "srt":
        return f"[完成] SRT: {srt_path}"
    return f"[完成] TXT: {txt_path} ({len(full_text)} 字, 语言: {detected_lang})"


def _fmt_srt(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    parser = argparse.ArgumentParser(description="本地语音转文字 (faster-whisper)")
    sub = parser.add_subparsers(dest="command")
    t = sub.add_parser("transcribe", help="转录音频文件")
    t.add_argument("audio", help="音频文件路径")
    t.add_argument("--model", default="base", help="模型大小 (tiny/base/small/medium/large-v3)")
    t.add_argument("--language", default=None, help="语言代码 (默认自动检测)")
    t.add_argument("--format", choices=["txt", "srt"], default="txt", help="输出格式")
    t.add_argument("--output-dir", default=None, help="输出目录")
    t.add_argument("--device", default="cpu", help="推理设备 cpu/auto")

    args = parser.parse_args()
    if args.command != "transcribe":
        parser.print_help()
        sys.exit(1)

    result = transcribe_file(
        args.audio,
        model_size=args.model,
        language=args.language,
        output_format=args.format,
        output_dir=args.output_dir,
        device=args.device,
    )
    print(result, flush=True)


if __name__ == "__main__":
    # UTF-8 stdout
    if sys.stdout.encoding and sys.stdout.encoding.upper() in ("GBK", "GB2312"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
