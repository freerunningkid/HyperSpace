#!/usr/bin/env python3
"""
computer-control MCP Server — 桌面控制能力

功能：
- screen_capture: 截屏（PIL ScreenGrab）
- mouse_move / mouse_click / double_click / right_click: 鼠标控制
- keyboard_type / keyboard_press: 键盘控制
- find_on_screen: 基于模板匹配的图像定位
- get_screen_size: 获取屏幕尺寸

依赖：Pillow, pyautogui, opencv-python
安装：pip install Pillow pyautogui opencv-python
"""

import json
import pyautogui
from pathlib import Path
from typing import Optional
import tempfile
import base64

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# 禁用 pyautogui 的失败暂停，提升速度
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.3


def handle_tool_call(name: str, args: dict) -> dict:
    """处理工具调用，返回标准 MCP 格式。"""
    try:
        if name == "screen_capture":
            path = args.get("path")
            if path:
                img = pyautogui.screenshot()
                img.save(path)
                return {"result": f"截图已保存: {path}"}
            else:
                img = pyautogui.screenshot()
                return {"result": "截图成功（未保存，可用 path 参数指定路径）"}

        elif name == "mouse_move":
            x = args["x"]
            y = args["y"]
            pyautogui.moveTo(x, y, duration=0.3)
            return {"result": f"鼠标移动到 ({x}, {y})"}

        elif name == "mouse_click":
            button = args.get("button", "left")
            pyautogui.click(button=button)
            return {"result": f"鼠标 {button} 单击"}

        elif name == "double_click":
            pyautogui.doubleClick()
            return {"result": "鼠标双击"}

        elif name == "right_click":
            pyautogui.rightClick()
            return {"result": "鼠标右键单击"}

        elif name == "mouse_drag":
            x = args.get("x", 0)
            y = args.get("y", 0)
            pyautogui.dragTo(x, y, duration=0.5)
            return {"result": f"鼠标拖拽到 ({x}, {y})"}

        elif name == "keyboard_type":
            text = args["text"]
            pyautogui.typewrite(text, interval=0.02)
            return {"result": f"输入文本: {text[:50]}{'...' if len(text)>50 else ''}"}

        elif name == "keyboard_press":
            key = args["key"]
            pyautogui.press(key)
            return {"result": f"按键: {key}"}

        elif name == "keyboard_hotkey":
            keys = args["keys"]
            pyautogui.hotkey(*keys)
            return {"result": f"热键: {'+'.join(keys)}"}

        elif name == "find_on_screen":
            if not HAS_CV2:
                return {"error": "需要安装 opencv-python 才能使用模板匹配"}
            template_path = args["template"]
            threshold = args.get("threshold", 0.8)
            img = cv2.imread(str(pyautogui.screenshot()), cv2.IMREAD_COLOR)
            tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if img is None or tpl is None:
                return {"error": "无法读取图片"}
            result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            if max_val >= threshold:
                cx = int(max_loc[0] + tpl.shape[1] / 2)
                cy = int(max_loc[1] + tpl.shape[0] / 2)
                return {"found": True, "x": cx, "y": cy, "confidence": float(max_val)}
            return {"found": False, "confidence": float(max_val)}

        elif name == "get_screen_size":
            w, h = pyautogui.size()
            return {"width": w, "height": h}

        elif name == "scroll":
            direction = args.get("direction", "down")
            clicks = args.get("clicks", 3)
            pyautogui.scroll(-clicks if direction == "down" else clicks)
            return {"result": f"滚动 {direction} {clicks} 格"}

        else:
            return {"error": f"未知工具: {name}"}

    except Exception as e:
        return {"error": str(e)}


def main():
    """简易 MCP 服务器，通过 stdin/stdout 通信。"""
    import sys
    print("computer-control MCP ready. Send JSONL requests on stdin.", flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            tool_name = req.get("name", "")
            tool_args = req.get("args", {})
            resp = handle_tool_call(tool_name, tool_args)
            print(json.dumps(resp, ensure_ascii=False))
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON: {e}"}))


if __name__ == "__main__":
    main()
