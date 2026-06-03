"""截图 OCR — 剪贴板 → 文件 → 多引擎识别 → 输出结果

用法:
  python clipboard_ocr.py                     # 默认竞速模式
  python clipboard_ocr.py --model ms-vl-30b   # ModelScope 免费快速版
  python clipboard_ocr.py --model paddle      # PaddleOCR-VL-1.6 版面解析
  python clipboard_ocr.py --model deepseek-ocr # 纯文字快速提取

工作流:
  截图 (Win+Shift+S / Alt+A / 微信) → 图片入剪贴板 → 运行此脚本
"""
import os, sys, time, subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_DIR = r"D:\Reasonix\截图"
OCR_SCRIPT = os.path.join(SCRIPT_DIR, "ocr.py")


def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # 1. 从剪贴板抓图
    try:
        from PIL import ImageGrab
    except ImportError:
        print("[错误] 缺少 Pillow 库，请运行: pip install Pillow")
        sys.exit(1)

    img = ImageGrab.grabclipboard()
    if img is None:
        print("[错误] 剪贴板中没有图片。请先截图（Win+Shift+S / Alt+A）再运行。")
        sys.exit(1)

    # 2. 保存
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(SCREENSHOT_DIR, f"screenshot_{timestamp}.png")
    img.save(save_path, "PNG")
    print(f"[保存] {save_path}", flush=True)

    # 3. OCR 识别
    extra_args = sys.argv[1:] if len(sys.argv) > 1 else []
    cmd = [sys.executable, OCR_SCRIPT, save_path] + extra_args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    elif result.stderr.strip():
        print(result.stderr.strip(), flush=True)
    sys.exit(result.returncode)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.upper() in ("GBK", "GB2312"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
