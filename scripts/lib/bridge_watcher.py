"""
桥文件监控 — 检测 ClaudeCode <-> Reasonix 2B 之间的新消息。

监控 D:/AgentWork/.claude/bridge-to-2b.md 的变化，
检测新的 --- 分隔符后的消息，朗读并提示。

用法:
  python bridge_watcher.py                       # 默认监控
  python bridge_watcher.py --speak               # 新消息自动朗读
"""
import os
import sys
import time
import json
import subprocess
from datetime import datetime

BRIDGE_FILE = r"D:\AgentWork\.claude\bridge-to-2b.md"
SPEAK_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speak.py")
WATCHED_BY = "Reasonix 2B"  # 本脚本代表谁

# 状态文件：记录已读消息的 hash
STATUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".claude", "status")
STATUS_FILE = os.path.join(STATUS_DIR, "bridge_watcher.json")


def _load_status():
    """加载已读消息记录"""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"read_hashes": [], "last_size": 0}


def _save_status(status):
    """保存已读消息记录"""
    os.makedirs(STATUS_DIR, exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def _hash_message(text: str) -> str:
    """简单 hash 消息内容去重"""
    return str(hash(text.strip()[:100]))


def _extract_new_messages(content: str, status: dict) -> list:
    """提取自从 last_size 以来新增的消息块"""
    current_size = len(content.encode("utf-8"))
    last_size = status.get("last_size", 0)

    if current_size <= last_size:
        return []

    # 按 --- 分割消息块
    blocks = content.split("\n---\n")
    new_blocks = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        h = _hash_message(block)
        if h not in status["read_hashes"]:
            new_blocks.append(block)
            status["read_hashes"].append(h)

    status["last_size"] = current_size
    return new_blocks


def _speak(text: str):
    """朗读文本"""
    try:
        if os.path.exists(SPEAK_SCRIPT):
            subprocess.Popen(
                [sys.executable, SPEAK_SCRIPT, text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
    except Exception:
        pass


def _get_sender(block: str) -> str:
    """判断消息发送者"""
    if "ClaudeCode" in block[:200]:
        return "ClaudeCode"
    if "Reasonix 2B" in block[:200]:
        return "Reasonix 2B"
    return "Unknown"


def watch(interval: float = 2.0, do_speak: bool = False):
    """监控桥文件"""
    if not os.path.exists(BRIDGE_FILE):
        print(f"[bridge-watcher] 桥文件不存在: {BRIDGE_FILE}")
        print(f"[bridge-watcher] 等待创建...")

    status = _load_status()

    print(f"[bridge-watcher] 监控 {BRIDGE_FILE}")
    print(f"[bridge-watcher] 间隔: {interval}s, 朗读: {do_speak}")
    print(f"[bridge-watcher] 代表: {WATCHED_BY}")
    print("")

    while True:
        try:
            if not os.path.exists(BRIDGE_FILE):
                time.sleep(interval)
                continue

            with open(BRIDGE_FILE, "r", encoding="utf-8") as f:
                content = f.read()

            new_msgs = _extract_new_messages(content, status)
            if new_msgs:
                for msg in new_msgs:
                    sender = _get_sender(msg)
                    # 只通知非本方的消息
                    if sender != WATCHED_BY:
                        lines = msg.split("\n")
                        preview = " ".join(
                            l for l in lines if l.strip() and not l.startswith("#") and not l.startswith("---")
                        )[:120]
                        ts = datetime.now().strftime("%H:%M:%S")
                        print(f"\n[{ts}] 💬 来自 {sender} 的新消息:")
                        print(f"    {preview}...")
                        if do_speak:
                            _speak(f"收到来自{sender}的消息: {preview[:80]}")
                    else:
                        # 自己的消息已处理
                        pass

                _save_status(status)

            time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[bridge-watcher] 已停止")
            break
        except Exception as e:
            print(f"[bridge-watcher] 错误: {e}", file=sys.stderr)
            time.sleep(interval)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="桥文件消息监控")
    parser.add_argument("--speak", action="store_true", help="新消息自动朗读")
    parser.add_argument("--interval", type=float, default=2.0, help="轮询间隔(秒)")
    args = parser.parse_args()
    watch(interval=args.interval, do_speak=args.speak)


if __name__ == "__main__":
    main()
