"""
backend.py - 桌面自动化后端服务
============================================================
功能：
  1. 接收指令（从命令行或队列文件）
  2. 路由到对应的执行引擎
  3. 将结果写入反馈文件
  4. 支持浏览器自动化（Midscene）和桌面自动化

用法：
  python scripts/lib/desktop_backend.py process "打开百度搜一下手机壳"
  python scripts/lib/desktop_backend.py queue "截个图"
  python scripts/lib/desktop_backend.py status

来源：ZCode auto-controller（迁移到 Reasonix 共享工具库）
"""

import subprocess
import sys
import os
import json
from datetime import datetime

# ---------- 配置 ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(SCRIPT_DIR, "指令队列.txt")
RESULT_FILE = os.path.join(SCRIPT_DIR, "反馈结果.txt")
LOG_FILE = os.path.join(SCRIPT_DIR, "backend.log")
PROJECT_ROOT = SCRIPT_DIR

# ---------- 日志 ----------
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ---------- 路由引擎 ----------
def route_command(command):
    cmd_lower = command.lower()
    
    if any(kw in cmd_lower for kw in ["打开", "搜索", "浏览", "网页", "百度", "google", "淘宝", "京东", "知乎", "b站", "youtube", "网站", "页面"]):
        return execute_browser(command)
    
    if any(kw in cmd_lower for kw in ["截图", "截屏", "screen", "capture"]):
        return execute_screenshot(command)
    
    if any(kw in cmd_lower for kw in ["打开", "关闭", "切换", "最小化", "最大化", "窗口"]):
        return execute_window(command)
    
    if any(kw in cmd_lower for kw in ["文件", "文件夹", "复制", "移动", "删除", "新建", "创建"]):
        return execute_file(command)
    
    return execute_generic(command)

def execute_browser(command):
    log(f"浏览器任务: {command}")
    script = generate_midscene_script(command)
    result = f"已生成 Midscene 脚本。请运行:\n  cd {PROJECT_ROOT}\\browser\n  node script.js\n\n脚本内容:\n{script}"
    return result

def execute_screenshot(command):
    log(f"截图任务: {command}")
    output_path = os.path.join(PROJECT_ROOT, "screenshots", f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    result = subprocess.run(
        ['powershell', '-Command', 
         f'$bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); '
         f'$g = [System.Drawing.Graphics]::FromImage($bmp); '
         f'$g.CopyFromScreen(0, 0, 0, 0); '
         f'$bmp.Save("{output_path}"); '
         f'$g.Dispose(); $bmp.Dispose()'],
        capture_output=True, text=True
    )
    
    if os.path.exists(output_path):
        return f"截图已保存: {output_path}"
    else:
        return "截图失败"

def execute_window(command):
    log(f"窗口任务: {command}")
    
    if "关闭" in command:
        title = command.replace("关闭", "").strip()
        subprocess.run(['powershell', '-Command', f'Get-Process | Where-Object {{$_ .MainWindowTitle -like "*{title}*"}} | Stop-Process -Force'], capture_output=True)
        return f"已尝试关闭: {title}"
    elif "打开" in command:
        app = command.replace("打开", "").strip()
        subprocess.run(['powershell', '-Command', f'Start-Process "{app}"'], capture_output=True)
        return f"已尝试打开: {app}"
    else:
        return f"窗口操作: {command}（待实现）"

def execute_file(command):
    log(f"文件任务: {command}")
    return f"文件操作: {command}（待实现）"

def execute_generic(command):
    log(f"通用任务: {command}")
    return f"指令已接收: {command}\n\n注意：这是一个通用指令，需要你手动确认或提供更多信息。"

# ---------- Midscene 脚本生成 ----------
def generate_midscene_script(command):
    if "搜索" in command or "搜" in command:
        keywords = command.replace("搜索", "").replace("搜一下", "").replace("百度", "").strip()
        return f'''const {{ vi }} = require('@midscene/web');
(async () => {{
  const page = await vi.autoSetup();
  await page.goto('https://www.baidu.com');
  // 输入搜索关键词: {keywords}
  await vi.sleep(2000);
  await vi.autoSaveSnapshot();
}})();'''
    elif "打开" in command:
        url = command.replace("打开", "").replace("网址", "").replace("链接", "").strip()
        return f'''const {{ vi }} = require('@midscene/web');
(async () => {{
  const page = await vi.autoSetup();
  await page.goto('{url}');
  await vi.sleep(2000);
  await vi.autoSaveSnapshot();
}})();'''
    else:
        return f'''const {{ vi }} = require('@midscene/web');
(async () => {{
  const page = await vi.autoSetup();
  // TODO: 解析指令 "{command}"
  await vi.sleep(1000);
}})();'''

# ---------- 主入口 ----------
def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python scripts/lib/desktop_backend.py process \"指令内容\"")
        print("  python scripts/lib/desktop_backend.py queue \"指令内容\"")
        print("  python scripts/lib/desktop_backend.py status")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "process":
        if len(sys.argv) < 3:
            print("缺少指令参数")
            sys.exit(1)
        command = " ".join(sys.argv[2:])
        result = route_command(command)
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            f.write(result)
        print(result)
    elif action == "queue":
        if len(sys.argv) < 3:
            print("缺少指令参数")
            sys.exit(1)
        command = " ".join(sys.argv[2:])
        with open(QUEUE_FILE, "a", encoding="utf-8") as f:
            f.write(command + "\n")
        log(f"指令已加入队列: {command}")
    elif action == "status":
        if os.path.exists(QUEUE_FILE):
            count = sum(1 for line in open(QUEUE_FILE, encoding="utf-8") if line.strip())
            print(f"队列中有 {count} 条指令")
        else:
            print("队列为空")
    else:
        print(f"未知动作: {action}")
        sys.exit(1)

if __name__ == "__main__":
    main()
