# -*- coding: utf-8 -*-
"""
web_vision —— DeepSeek 网页端识图 (实验/个人用, 违 ToS).

CLI: 传入一张图片 → 用 Playwright 自动化 DeepSeek 网页端对话 → 打印识图结果.

用法:
    python -m hyperspace.experimental.web_vision --image path/to/photo.jpg
    python -m hyperspace.experimental.web_vision --image https://example.com/photo.png --prompt "What is this?"

首次运行会打开浏览器窗口, 请手动扫码登录; 之后自动复用登录态.
本模块严格隔离: 不接入 MCP, 不被 server.py import.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

from .session import close_session, get_session

# ── 默认提示词 ──
DEFAULT_PROMPT = "请详细描述这张图片"


def _normalize_image(image_arg: str) -> Path | str:
    """处理图片参数: 本地路径或 URL."""
    path = Path(image_arg)
    if path.exists():
        return path.resolve()
    # 不是本地文件, 当作 URL 或 data URI 原样传递
    return image_arg


def _upload_image(page, image: Path | str) -> None:
    """将图片上传到 DeepSeek 对话输入框.

    策略: 先尝试找文件上传按钮 → 触发文件选择器 → 设文件.
    兜底: 直接用 set_input_files 设 hidden input.
    """
    # 策略 A: 通过文件选择器上传
    try:
        # 查找上传按钮 (通常是一个 + 或 📎 图标)
        upload_btn = page.locator(
            "button:has(svg), button:has-text('+'), "
            "div[role='button']:has(svg), "
            "button[aria-label*='upload' i], button[aria-label*='attach' i], "
            "button[aria-label*='image' i]"
        ).first
        if upload_btn.is_visible(timeout=2000):
            with page.expect_file_chooser() as fc_info:
                upload_btn.click()
            file_chooser = fc_info.value
            if isinstance(image, Path):
                file_chooser.set_files(str(image))
            else:
                # URL: 无法直接设置; 退出用兜底
                raise RuntimeError("URL upload not supported via file chooser")
            print(f"[web_vision] 📎 已上传文件: {image}", file=sys.stderr, flush=True)
            # 等上传完成后出现预览
            page.wait_for_timeout(2000)
            return
    except Exception as e:
        print(f"[web_vision] 策略A失败: {e}, 尝试兜底...", file=sys.stderr, flush=True)

    # 策略 B: 直接 set_input_files (如果有 hidden file input)
    try:
        file_input = page.locator("input[type='file']").first
        if file_input.is_visible(timeout=1000) or True:  # hidden 也行
            if isinstance(image, Path):
                file_input.set_input_files(str(image))
                print(f"[web_vision] 📎 已通过 file input 上传: {image}", file=sys.stderr, flush=True)
                page.wait_for_timeout(2000)
                return
    except Exception as e:
        print(f"[web_vision] 策略B失败: {e}, 尝试粘贴...", file=sys.stderr, flush=True)

    # 策略 C: 粘贴本地图片 (适用于支持粘贴的输入框)
    if isinstance(image, Path) and image.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        try:
            # 浏览器支持 clipboard paste, 但 Playwright 没有原生 paste 方法
            # 可以用 page.evaluate 构造 DataTransfer + paste event
            img_b64 = base64.b64encode(image.read_bytes()).decode("ascii")
            mime = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp",
            }.get(image.suffix.lower(), "image/jpeg")
            data_url = f"data:{mime};base64,{img_b64}"

            # 通过 JS 在输入框上触发 paste 事件
            input_box = page.locator("textarea, div[contenteditable='true']").first
            input_box.click()
            page.evaluate(
                """
                (data_url) => {
                    const dt = new DataTransfer();
                    fetch(data_url).then(r => r.blob()).then(blob => {
                        const file = new File([blob], 'image.png', { type: blob.type });
                        dt.items.add(file);
                        const el = document.activeElement;
                        el.dispatchEvent(new ClipboardEvent('paste', {
                            clipboardData: dt,
                            bubbles: true,
                            cancelable: true,
                        }));
                    });
                    return 'pasted';
                }
                """,
                data_url,
            )
            print(f"[web_vision] 📎 已粘贴图片: {image}", file=sys.stderr, flush=True)
            page.wait_for_timeout(3000)
            return
        except Exception as e:
            print(f"[web_vision] 策略C失败: {e}", file=sys.stderr, flush=True)

    raise RuntimeError(f"无法上传图片: {image}")


def _send_and_wait(page, prompt: str, timeout: int = 120) -> str:
    """在输入框填入 prompt → 发送 → 等待流式完成 → 返回回复文本."""
    # 1. 定位输入框
    input_box = page.locator("textarea, div[contenteditable='true']").first
    input_box.click()
    page.wait_for_timeout(300)

    # 2. 输入 prompt
    input_box.fill(prompt)
    page.wait_for_timeout(500)

    # 3. 发送
    input_box.press("Enter")
    print(f"[web_vision] ✉ 已发送: {prompt[:60]}...", file=sys.stderr, flush=True)

    # 4. 等待流式输出完成
    # 检测「停止生成」按钮出现 → 消失, 或文本稳定
    deadline = time.time() + timeout
    last_text = ""
    stable_rounds = 0

    while time.time() < deadline:
        time.sleep(1.0)
        # 尝试定位回复容器
        messages = page.locator(".ds-markdown, .markdown-body, .prose, article, [data-testid='message-content']")
        count = messages.count()
        if count == 0:
            continue

        current = messages.last.text_content() or ""
        if current == last_text:
            stable_rounds += 1
            if stable_rounds >= 3:  # 连续 3 秒无变化 → 完成
                break
        else:
            stable_rounds = 0
            last_text = current

    # 额外缓冲
    page.wait_for_timeout(500)

    # 5. 提取最后一条回复
    messages = page.locator(".ds-markdown, .markdown-body, .prose, article, [data-testid='message-content']")
    text = ""
    if messages.count() > 0:
        text = messages.last.text_content() or ""
    return text.strip()


def main():
    parser = argparse.ArgumentParser(
        description="DeepSeek 网页端识图 (个人实验)",
        epilog="首次运行会弹出浏览器, 请手动扫码登录.",
    )
    parser.add_argument(
        "--image", "-i", required=True,
        help="图片路径或 URL",
    )
    parser.add_argument(
        "--prompt", "-p", default=DEFAULT_PROMPT,
        help=f"提问文字 (默认: {DEFAULT_PROMPT})",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="无头模式 (默认 False, 首次需 headed 登录)",
    )
    args = parser.parse_args()

    image = _normalize_image(args.image)
    print(f"[web_vision] 🖼 图片: {image}", file=sys.stderr, flush=True)
    print(f"[web_vision] 💬 提示: {args.prompt}", file=sys.stderr, flush=True)

    # 启动 session
    page, context, pw = get_session(headless=args.headless)

    try:
        # 上传图片
        _upload_image(page, image)

        # 发送 + 等待回复
        result = _send_and_wait(page, args.prompt)

        # 打印结果 (stdout, 纯文本)
        print("\n" + "=" * 50)
        print(result)
        print("=" * 50)

        # 保存登录态
        context.storage_state(
            path=str(Path(__file__).resolve().parent.parent.parent / "data" / "deepseek_session.json")
        )

    finally:
        close_session(page, context, pw)


if __name__ == "__main__":
    main()
