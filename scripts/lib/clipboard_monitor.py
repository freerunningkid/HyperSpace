"""
剪贴板截图监视器 — 自动保存截图 + GPT-4o 识别（加固版）

特性:
  - 单实例锁（防重复启动）
  - 连续错误上限 → 自动退出（防死循环）
  - 剪贴板异常容错
  - API 调用超时保护
  - 日志写入文件

用法:
  python clipboard_monitor.py                # 前台运行
  pythonw clipboard_monitor.py               # 后台无窗口（配合 VBS 启动）
"""

import os
import sys
import time
import json
import hashlib
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from PIL import ImageGrab
except ImportError:
    print("[错误] 需要安装 Pillow: pip install Pillow")
    sys.exit(1)

from ocr import ocr as ocr_analyze

# ── 配置 ──
SAVE_DIR = Path(r"D:\Reasonix\screenshots-截图")
LOG_DIR = Path(r"D:\Reasonix\screenshots-截图")
MODEL = "gpt-4o"
POLL_INTERVAL = 1.0          # 剪贴板轮询间隔（秒）
MAX_CONSEC_ERRORS = 10        # 连续错误上限（超过即退出）
LOCK_FILE = Path(r"D:\Reasonix\.screenshot_monitor.lock")

DEFAULT_PROMPT = (
    "请识别这张截图："
    "1）如果包含文字，完整提取所有文字内容；"
    "2）如果没有文字，详细描述图片中的场景、界面、元素等内容；"
    "3）在回答末尾用一行注明图片类型（如：聊天截图、网页、代码编辑器、文档、表格、海报等）。"
)


def log(msg: str):
    """同时输出到控制台和日志文件"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / "monitor.log"
        # 自动轮转：超过 1MB 清空
        if log_file.exists() and log_file.stat().st_size > 1_000_000:
            bak = LOG_DIR / f"monitor-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            log_file.rename(bak)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def acquire_lock() -> bool:
    """获取单实例锁。已存在则检查进程是否存活，死进程则接管。"""
    if LOCK_FILE.exists():
        try:
            data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            pid = data.get("pid", 0)
            if pid:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
                if handle:
                    kernel32.CloseHandle(handle)
                    log(f"监视器已在运行 (PID {pid})，退出")
                    return False
                # 进程不存在，可以接管
                log(f"检测到僵尸锁 (PID {pid} 已不存在)，接管")
        except Exception:
            pass

    LOCK_FILE.write_text(json.dumps({
        "pid": os.getpid(),
        "started": datetime.now().isoformat()
    }), encoding="utf-8")
    return True


def release_lock():
    """释放单实例锁"""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


def image_hash(img) -> str:
    """计算图片 MD5，用于去重"""
    return hashlib.md5(img.tobytes()).hexdigest()


def save_image(img, save_dir: Path) -> Path:
    """保存图片，返回文件路径"""
    save_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = save_dir / f"shot-{ts}.png"
    img.save(str(path), "PNG")
    return path


def main():
    # 单实例检查
    if not acquire_lock():
        sys.exit(0)

    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)

        log("🔍 截图监视器启动")
        log(f"   保存目录: {SAVE_DIR}")
        log(f"   识别引擎: {MODEL}")
        log(f"   快捷键: Shift+Win+S / Alt+A")
        log("-" * 40)

        last_hash = None
        consecutive_errors = 0

        while True:
            try:
                img = ImageGrab.grabclipboard()
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors == 1:
                    log(f"⚠️ 剪贴板读取异常: {e}")
                if consecutive_errors >= MAX_CONSEC_ERRORS:
                    log(f"❌ 连续 {MAX_CONSEC_ERRORS} 次剪贴板错误，退出")
                    break
                time.sleep(max(POLL_INTERVAL, 5.0))  # 出错时等久一点
                continue

            consecutive_errors = 0  # 成功读取即重置

            if img is not None:
                try:
                    h = image_hash(img)
                except Exception:
                    time.sleep(POLL_INTERVAL)
                    continue

                if h != last_hash:
                    last_hash = h

                    try:
                        filepath = save_image(img, SAVE_DIR)
                        log(f"📸 新截图 → {filepath.name}")
                    except Exception as e:
                        log(f"❌ 保存失败: {e}")
                        time.sleep(POLL_INTERVAL)
                        continue

                    # GPT-4o 识别
                    try:
                        result = ocr_analyze(str(filepath), prompt=DEFAULT_PROMPT, model=MODEL)
                        if result and not result.startswith("[错误]"):
                            log("   🤖 识别完成:")
                            for line in result.split("\n"):
                                log(f"      {line}")
                            log("-" * 40)
                        else:
                            log(f"   ⚠️ {result}")
                    except Exception as e:
                        log(f"   ❌ 识别异常: {e}")

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        log("👋 用户中断，退出")
    except Exception as e:
        log(f"💥 未捕获异常: {e}")
        log(traceback.format_exc())
    finally:
        release_lock()
        log("监视器已退出")


if __name__ == "__main__":
    main()
