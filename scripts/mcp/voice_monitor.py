#!/usr/bin/env python3
"""Voice Monitor — watch Reasonix session JSONL for new assistant replies → auto TTS.

Run alongside Reasonix. Watches the latest session JSONL file,
detects assistant responses, and speaks them automatically.
No model involvement needed — purely file-watch based.

Usage:
  python voice_monitor.py              # watch latest session
  python voice_monitor.py --session <id>  # watch specific session
"""

import json
import os
import sys
import time
import subprocess
import argparse

SESSION_DIR = os.path.expanduser(r"~\.reasonix\sessions")
SPEAK_SCRIPT = r"D:\AgentWork\scripts\tools\speak.py"


def find_latest_session() -> str | None:
    """Find the most recently modified session JSONL file."""
    if not os.path.isdir(SESSION_DIR):
        return None
    jsonl_files = [
        os.path.join(SESSION_DIR, f)
        for f in os.listdir(SESSION_DIR)
        if f.endswith(".jsonl") and not f.endswith(".bak")
    ]
    if not jsonl_files:
        return None
    return max(jsonl_files, key=os.path.getmtime)


def extract_text(line: str) -> str | None:
    """Extract text content from an assistant message JSONL line."""
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return None
    if msg.get("role") != "assistant":
        return None
    content = msg.get("content", "")
    if not content:
        return None
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        content = "\n".join(texts)
    return content.strip() if content.strip() else None


def speak(text: str) -> None:
    """Speak text in a detached background process."""
    try:
        subprocess.Popen(
            [sys.executable, SPEAK_SCRIPT, text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | 0x00000008,
        )
    except Exception:
        pass


def watch(session_path: str, poll_interval: float = 0.5):
    """Watch a session JSONL file and speak new assistant messages."""
    if not os.path.exists(SPEAK_SCRIPT):
        print(f"[voice-monitor] speak.py not found: {SPEAK_SCRIPT}", file=sys.stderr)
        return

    print(f"[voice-monitor] 监控 {session_path}", file=sys.stderr, flush=True)

    # Start from the end of file (don't replay old messages)
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)
    except FileNotFoundError:
        # File doesn't exist yet — wait for it
        pass

    last_size = os.path.getsize(session_path) if os.path.exists(session_path) else 0
    spoken = set()  # track spoken messages by content hash (avoid duplicates)

    while True:
        try:
            if not os.path.exists(session_path):
                time.sleep(poll_interval)
                continue

            current_size = os.path.getsize(session_path)
            if current_size > last_size:
                with open(session_path, "r", encoding="utf-8") as f:
                    f.seek(last_size)
                    new_data = f.read()
                last_size = current_size

                for line in new_data.strip().split("\n"):
                    text = extract_text(line)
                    if text:
                        h = hash(text)
                        if h not in spoken:
                            spoken.add(h)
                            print(f"[voice-monitor] 🎤 朗读 ({len(text)}字)", file=sys.stderr, flush=True)
                            speak(text)

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("[voice-monitor] 已停止", file=sys.stderr)
            break
        except Exception as e:
            print(f"[voice-monitor] 错误: {e}", file=sys.stderr)
            time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Voice Monitor for Reasonix")
    parser.add_argument("--session", help="Session ID to watch")
    args = parser.parse_args()

    if args.session:
        session_path = os.path.join(SESSION_DIR, f"{args.session}.jsonl")
        if not os.path.exists(session_path):
            print(f"[voice-monitor] 会话不存在: {args.session}", file=sys.stderr)
            sys.exit(1)
    else:
        session_path = find_latest_session()
        if not session_path:
            print("[voice-monitor] 没有找到会话文件，等待中...", file=sys.stderr)
            # Wait for a session to appear
            for _ in range(30):
                time.sleep(1)
                session_path = find_latest_session()
                if session_path:
                    break
            if not session_path:
                print("[voice-monitor] 超时：没有检测到会话", file=sys.stderr)
                sys.exit(1)

    watch(session_path)


if __name__ == "__main__":
    main()
