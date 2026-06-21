"""
bridge.py - 桌面自动化统一桥接层（v2）
============================================================
覆盖能力：
  - 截图（全屏/窗口）
  - 窗口管理（打开/关闭/最小化/最大化/激活）
  - 鼠标操作（点击/双击/右键/拖拽/移动）
  - 键盘操作（输入文字/快捷键）
  - 文件操作（复制/移动/删除/创建/列表）
  - 命令行执行（git/npm/python/node/任意命令）
  - 剪贴板（读/写）
  - 浏览器自动化（Playwright）
  - 分级安全确认（危险操作需二次确认）

用法：
  python scripts/lib/desktop_bridge.py "截个图"
  python scripts/lib/desktop_bridge.py "打开记事本"
  python scripts/lib/desktop_bridge.py "复制文件 D:\\a.txt 到 D:\\b.txt"
  python scripts/lib/desktop_bridge.py "运行命令 echo hello"

来源：ZCode auto-controller（迁移到 Reasonix 共享工具库）
"""

import subprocess
import sys
import os
import re
import shutil
import json
from datetime import datetime
from pathlib import Path


# ---------- 配置 ----------
PROJECT_ROOT = Path(__file__).parent
BROWSER_DIR = PROJECT_ROOT / "browser"
SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
LOG_FILE = PROJECT_ROOT / "bridge.log"

SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 危险操作关键词（触发分级确认） ----------
DANGEROUS_KEYWORDS = ["删除", "格式化", "支付", "付款", "登录", "提交", "清空", "remove", "delete", "format"]
DANGEROUS_COMMANDS = ["del ", "rm ", "rmdir", "format", "shutdown", "taskkill"]

# ---------- 日志 ----------
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ---------- 安全确认 ----------
def is_dangerous(command):
    cmd_lower = command.lower()
    if any(kw in command for kw in DANGEROUS_KEYWORDS):
        return True
    if any(kw in cmd_lower for kw in DANGEROUS_COMMANDS):
        return True
    return False

def confirm_dangerous(command):
    """危险操作弹窗确认。命令行模式下默认拒绝（安全起见）。"""
    return f"⚠️ 危险操作需确认：{command}\n请在对话中明确授权后重试。"

# ---------- 指令分类器 ----------
def classify_command(cmd):
    """根据关键词分类指令（按优先级排序）"""
    cmd_lower = cmd.lower()
    
    # 1. 截图
    if any(kw in cmd for kw in ["截图", "截屏", "截个图", "拍照"]) or "capture" in cmd_lower or "screenshot" in cmd_lower:
        return "screenshot"
    
    # 2. 文件操作
    if any(kw in cmd for kw in ["复制文件", "移动文件", "删除文件", "新建文件", "创建文件", "文件列表", "列出文件"]):
        return "file"
    
    # 3. 命令行执行
    if any(kw in cmd for kw in ["运行命令", "执行命令", "跑命令"]) or cmd.lower().startswith(("git ", "npm ", "node ", "python ")):
        return "cmd"
    
    # 4. 剪贴板
    if any(kw in cmd for kw in ["读剪贴板", "写剪贴板", "复制到剪贴板"]):
        return "clipboard"
    
    # 5. 鼠标/键盘（桌面GUI）
    if any(kw in cmd for kw in ["点击", "双击", "右键", "拖拽", "移动鼠标", "输入文字", "按键", "快捷键"]):
        return "input"
    
    # 6. 窗口管理
    if any(kw in cmd for kw in ["最小化", "最大化", "关闭窗口", "激活窗口", "切换窗口"]):
        return "window"
    
    # 7. 打开应用（精确匹配）
    if any(kw in cmd for kw in ["记事本", "notepad", "calc", "计算器", "打开应用", "启动"]):
        return "app"
    
    # 8. 浏览器
    if any(kw in cmd for kw in ["打开", "浏览", "搜索", "搜一下", "百度", "bing", "google", 
                                 "淘宝", "京东", "知乎", "网站", "页面", "http", "www"]):
        return "browser"
    
    return "generic"

# ============================================================
# 执行引擎
# ============================================================

def execute_screenshot_command(command):
    """截图：全屏"""
    log(f"截图命令: {command}")
    import pyautogui
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = SCREENSHOT_DIR / f"screenshot_{timestamp}.png"
    img = pyautogui.screenshot()
    img.save(str(output_path))
    return f"截图已保存: {output_path}"

def execute_file_command(command):
    """文件操作：复制/移动/删除/创建/列表"""
    log(f"文件命令: {command}")
    
    if "复制文件" in command:
        m = re.search(r'复制文件\s+(.+?)\s+到\s+(.+)', command)
        if m:
            src, dst = m.group(1).strip(), m.group(2).strip()
            shutil.copy2(src, dst)
            return f"已复制: {src} -> {dst}"
        return "格式: 复制文件 <源> 到 <目标>"
    
    if "移动文件" in command:
        m = re.search(r'移动文件\s+(.+?)\s+到\s+(.+)', command)
        if m:
            src, dst = m.group(1).strip(), m.group(2).strip()
            shutil.move(src, dst)
            return f"已移动: {src} -> {dst}"
        return "格式: 移动文件 <源> 到 <目标>"
    
    if "删除文件" in command:
        if is_dangerous(command):
            return confirm_dangerous(command)
        m = re.search(r'删除文件\s+(.+)', command)
        if m:
            path = m.group(1).strip()
            p = Path(path)
            if p.is_file():
                p.unlink()
                return f"已删除文件: {path}"
            elif p.is_dir():
                shutil.rmtree(p)
                return f"已删除目录: {path}"
            return f"路径不存在: {path}"
        return "格式: 删除文件 <路径>"
    
    if "新建文件" in command or "创建文件" in command:
        m = re.search(r'(?:新建|创建)文件\s+(.+)', command)
        if m:
            path = m.group(1).strip()
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).touch()
            return f"已创建文件: {path}"
        return "格式: 新建文件 <路径>"
    
    if "文件列表" in command or "列出文件" in command:
        m = re.search(r'(?:文件列表|列出文件)\s+(.+)', command)
        dirpath = m.group(1).strip() if m else "."
        try:
            entries = sorted(Path(dirpath).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            lines = []
            for e in entries[:50]:
                prefix = "[目录] " if e.is_dir() else "[文件] "
                size = f" ({e.stat().st_size} 字节)" if e.is_file() else ""
                lines.append(f"{prefix}{e.name}{size}")
            return f"目录 {dirpath}（共 {len(entries)} 项，显示前50）:\n" + "\n".join(lines)
        except Exception as ex:
            return f"读取目录失败: {ex}"
    
    return f"未识别的文件操作: {command}"

def execute_cmd_command(command):
    """命令行执行"""
    log(f"命令行命令: {command}")
    
    for prefix in ["运行命令", "执行命令", "跑命令"]:
        if command.startswith(prefix):
            actual_cmd = command[len(prefix):].strip()
            break
    else:
        actual_cmd = command
    
    if is_dangerous(actual_cmd):
        return confirm_dangerous(actual_cmd)
    
    try:
        result = subprocess.run(
            actual_cmd, shell=True, capture_output=True, text=True, encoding="utf-8", timeout=60
        )
        output = result.stdout.strip() if result.stdout else ""
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr.strip()}"
        return f"命令: {actual_cmd}\n退出码: {result.returncode}\n输出:\n{output}"
    except subprocess.TimeoutExpired:
        return f"命令超时（60秒）: {actual_cmd}"
    except Exception as ex:
        return f"执行失败: {ex}"

def execute_clipboard_command(command):
    """剪贴板读写"""
    log(f"剪贴板命令: {command}")
    import pyperclip
    
    if "读剪贴板" in command:
        content = pyperclip.paste()
        return f"剪贴板内容:\n{content}"
    
    if "写剪贴板" in command or "复制到剪贴板" in command:
        m = re.search(r'(?:写剪贴板|复制到剪贴板)\s+(.+)', command)
        if m:
            text = m.group(1).strip()
            pyperclip.copy(text)
            return f"已写入剪贴板: {text}"
        return "格式: 写剪贴板 <内容>"
    
    return f"未识别的剪贴板操作: {command}"

def execute_input_command(command):
    """鼠标/键盘操作（pyautogui）"""
    log(f"输入命令: {command}")
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.3
    
    if "点击" in command and "双击" not in command and "右键" not in command:
        m = re.search(r'点击\s+(\d+)\s+(\d+)', command)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            pyautogui.click(x, y)
            return f"已点击: ({x}, {y})"
        return "格式: 点击 <x> <y>"
    
    if "双击" in command:
        m = re.search(r'双击\s+(\d+)\s+(\d+)', command)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            pyautogui.doubleClick(x, y)
            return f"已双击: ({x}, {y})"
        return "格式: 双击 <x> <y>"
    
    if "右键" in command:
        m = re.search(r'右键\s+(\d+)\s+(\d+)', command)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            pyautogui.rightClick(x, y)
            return f"已右键: ({x}, {y})"
        return "格式: 右键 <x> <y>"
    
    if "拖拽" in command:
        m = re.search(r'拖拽\s+(\d+)\s+(\d+)\s+到\s+(\d+)\s+(\d+)', command)
        if m:
            x1, y1, x2, y2 = [int(g) for g in m.groups()]
            pyautogui.dragTo(x2, y2, duration=0.5, _pause=False)
            return f"已拖拽: ({x1},{y1}) -> ({x2},{y2})"
        return "格式: 拖拽 <x1> <y1> 到 <x2> <y2>"
    
    if "移动鼠标" in command:
        m = re.search(r'移动鼠标\s+(\d+)\s+(\d+)', command)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            pyautogui.moveTo(x, y, duration=0.3)
            return f"鼠标已移动到: ({x}, {y})"
        return "格式: 移动鼠标 <x> <y>"
    
    if "输入文字" in command:
        m = re.search(r'输入文字\s+(.+)', command)
        if m:
            text = m.group(1).strip()
            pyautogui.typewrite(text, interval=0.05) if text.isascii() else pyautogui.write(text)
            return f"已输入文字: {text}"
        return "格式: 输入文字 <内容>"
    
    if "快捷键" in command or "按键" in command:
        m = re.search(r'(?:快捷键|按键)\s+(.+)', command)
        if m:
            keys = [k.strip() for k in re.split(r'[+＋]', m.group(1))]
            pyautogui.hotkey(*keys)
            return f"已按快捷键: {'+'.join(keys)}"
        return "格式: 快捷键 <键1>+<键2>（如 ctrl+c）"
    
    return f"未识别的输入操作: {command}"

def execute_window_command(command):
    """窗口管理（pygetwindow）"""
    log(f"窗口命令: {command}")
    import pygetwindow as gw
    
    if "最小化" in command:
        m = re.search(r'最小化\s+(.+)', command)
        if m:
            title = m.group(1).strip()
            wins = [w for w in gw.getAllWindows() if title.lower() in w.title.lower()]
            if wins:
                wins[0].minimize()
                return f"已最小化: {wins[0].title}"
            return f"未找到窗口: {title}"
        return "格式: 最小化 <窗口标题>"
    
    if "最大化" in command:
        m = re.search(r'最大化\s+(.+)', command)
        if m:
            title = m.group(1).strip()
            wins = [w for w in gw.getAllWindows() if title.lower() in w.title.lower()]
            if wins:
                wins[0].maximize()
                return f"已最大化: {wins[0].title}"
            return f"未找到窗口: {title}"
        return "格式: 最大化 <窗口标题>"
    
    if "关闭窗口" in command:
        if is_dangerous(command):
            return confirm_dangerous(command)
        m = re.search(r'关闭窗口\s+(.+)', command)
        if m:
            title = m.group(1).strip()
            wins = [w for w in gw.getAllWindows() if title.lower() in w.title.lower()]
            if wins:
                wins[0].close()
                return f"已关闭窗口: {wins[0].title}"
            return f"未找到窗口: {title}"
        return "格式: 关闭窗口 <窗口标题>"
    
    if "激活窗口" in command or "切换窗口" in command:
        m = re.search(r'(?:激活窗口|切换窗口)\s+(.+)', command)
        if m:
            title = m.group(1).strip()
            wins = [w for w in gw.getAllWindows() if title.lower() in w.title.lower()]
            if wins:
                wins[0].activate()
                return f"已激活窗口: {wins[0].title}"
            return f"未找到窗口: {title}"
        return "格式: 激活窗口 <窗口标题>"
    
    return f"未识别的窗口操作: {command}"

def execute_app_command(command):
    """打开应用"""
    log(f"应用命令: {command}")
    if "打开" in command or "启动" in command:
        app = command.replace("打开", "").replace("启动", "").replace("应用", "").strip()
        app_map = {
            "记事本": "notepad.exe",
            "计算器": "calc.exe",
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "画图": "mspaint.exe",
            "资源管理器": "explorer.exe",
            "任务管理器": "taskmgr.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
        }
        exe = app_map.get(app.lower(), app)
        try:
            subprocess.Popen(["start", "", exe], shell=True)
            return f"已启动应用: {exe}"
        except Exception as ex:
            return f"启动失败: {ex}"
    return f"未识别的应用操作: {command}"

def execute_browser_command(command):
    """浏览器自动化（Playwright）"""
    log(f"浏览器命令: {command}")
    
    script = generate_browser_script(command)
    script_path = BROWSER_DIR / "auto_script.js"
    script_path.write_text(script, encoding="utf-8")
    
    try:
        result = subprocess.run(
            ["node", str(script_path)],
            cwd=str(BROWSER_DIR),
            capture_output=True, text=True, encoding="utf-8", timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip() or "(浏览器任务完成)"
        return f"浏览器执行失败: {result.stderr.strip().split(chr(10))[-1]}"
    except subprocess.TimeoutExpired:
        return "浏览器任务超时（60秒）"
    except Exception as ex:
        return f"浏览器执行异常: {ex}"

def generate_browser_script(command):
    """生成 Playwright 脚本"""
    cmd_lower = command.lower()
    browser_dir_str = str(BROWSER_DIR).replace("\\", "/")
    screenshot_dir_str = str(SCREENSHOT_DIR).replace("\\", "/")
    
    if "本地" in command or "test-page" in cmd_lower:
        return f'''const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch({{ headless: false }});
  const page = await browser.newPage();
  await page.goto('file:///{browser_dir_str}/test-page.html', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForTimeout(1500);
  await page.screenshot({{ path: '{screenshot_dir_str}/browser_local.png' }});
  console.log('已打开本地页面，截图已保存');
  await browser.close();
}})();'''
    
    if "搜索" in command or "搜" in command:
        keyword = re.sub(r'.*?(搜索|搜一下|在百度上搜|百度搜)', '', command).strip()
        if not keyword:
            keyword = command.replace("搜索", "").replace("搜一下", "").replace("百度", "").strip()
        return f'''const {{ chromium }} = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {{
  const browser = await chromium.launch({{ headless: false }});
  const page = await browser.newPage();
  try {{
    await page.goto('https://cn.bing.com/?q={keyword}', {{ waitUntil: 'domcontentloaded', timeout: 20000 }});
    await page.waitForTimeout(3000);
    await page.screenshot({{ path: path.join('{screenshot_dir_str}', 'search_result.png'), fullPage: true }});
    console.log('已搜索: {keyword}');
    console.log('截图: {screenshot_dir_str}/search_result.png');
  }} catch(e) {{
    console.log('搜索失败(可能网络问题): ' + e.message.split('\\\\n')[0]);
  }}
  await browser.close();
}})();'''
    
    if "打开" in command:
        target = command.replace("打开", "").strip()
        if target == "浏览器" or target == "chrome" or target == "edge":
            target = "about:blank"
        elif not target.startswith("http"):
            target = "https://" + (target if "." in target else "www." + target + ".com")
        return f'''const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch({{ headless: false }});
  const page = await browser.newPage();
  try {{
    await page.goto('{target}', {{ waitUntil: 'domcontentloaded', timeout: 20000 }});
    await page.waitForTimeout(2000);
    console.log('已打开: {target}');
  }} catch(e) {{
    console.log('打开失败(可能网络问题): ' + e.message.split('\\\\n')[0]);
  }}
  await browser.close();
}})();'''
    
    return "console.log('无法解析浏览器指令: " + command + "');process.exit(1);"

def execute_generic_command(command):
    """通用处理：列出所有可用指令"""
    log(f"通用命令: {command}")
    return f"""指令未识别: {command}

支持的指令格式：
【截图】截个图
【窗口】打开记事本 | 最小化 记事本 | 最大化 记事本 | 关闭窗口 记事本 | 激活窗口 记事本
【鼠标】点击 100 200 | 双击 100 200 | 右键 100 200 | 拖拽 100 200 到 300 400 | 移动鼠标 100 200
【键盘】输入文字 你好 | 快捷键 ctrl+c
【文件】复制文件 D:\\a.txt 到 D:\\b.txt | 移动文件 ... 到 ... | 删除文件 ... | 新建文件 ... | 文件列表 D:\\folder
【命令】运行命令 echo hello | 运行命令 git status
【剪贴板】读剪贴板 | 写剪贴板 你好
【浏览器】打开本地页面 | 搜索 手机壳 | 打开 www.bing.com"""

# ---------- 主路由 ----------
def route_command(command):
    category = classify_command(command)
    
    if is_dangerous(command):
        return confirm_dangerous(command)
    
    routers = {
        "screenshot": execute_screenshot_command,
        "file": execute_file_command,
        "cmd": execute_cmd_command,
        "clipboard": execute_clipboard_command,
        "input": execute_input_command,
        "window": execute_window_command,
        "app": execute_app_command,
        "browser": execute_browser_command,
        "generic": execute_generic_command,
    }
    
    handler = routers.get(category, execute_generic_command)
    try:
        return handler(command)
    except Exception as ex:
        log(f"执行异常: {ex}")
        return f"执行失败: {ex}"

# ---------- 主入口 ----------
def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--param-file":
        param_file = sys.argv[2]
        try:
            with open(param_file, "r", encoding="utf-8") as f:
                command = f.read().strip()
        except Exception as ex:
            print(f"读取参数文件失败: {ex}")
            sys.exit(1)
    elif len(sys.argv) < 2:
        print(execute_generic_command(""))
        sys.exit(1)
    else:
        command = " ".join(sys.argv[1:])
    
    print(command)
    print("-" * 50)
    result = route_command(command)
    print("\n" + "=" * 50)
    print(result)
    print("=" * 50)

if __name__ == "__main__":
    main()
