---
name: desktop-automation
description: 桌面操控工作流 — AHK 键鼠模拟 + mss 截图 + pyperclip 剪贴板 + win32com 窗口管理 + 文件操作
---

# 桌面自动化工作流

## 工具速查

| 工具 | 安装状态 | 调用方式 |
|------|---------|---------|
| **AutoHotkey v2** | ✅ | `"C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe" script.ahk` |
| **mss（截图）** | ✅ pip | `python -c "import mss; ..."` |
| **pyperclip（剪贴板）** | ✅ pip | `python -c "import pyperclip; pyperclip.copy('...')"` |
| **win32com（窗口）** | ✅ pip | `python -c "import win32com.client; ..."` |
| **Everything CLI** | ✅ | `"D:/Software/Everything/es.exe" <keyword>` |
| **pwsh（PowerShell）** | ✅ v7.6 | `pwsh -Command "..."` |

---

## 工作流

### 1. ⌨️ AHK 键鼠模拟

```bash
# 基础点击 + 输入
echo '
Click 500 300
Send "Hello World{Enter}"
' > /tmp/tmp.ahk && "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe" /tmp/tmp.ahk

# 等待窗口出现再操作
echo '
WinWait "计算器"
WinActivate "计算器"
Send "123+456="
Sleep 500
' > /tmp/tmp.ahk && "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe" /tmp/tmp.ahk

# 组合键
echo '
Send "^c"     ; Ctrl+C 复制
Send "^v"     ; Ctrl+V 粘贴
Send "!{F4}"  ; Alt+F4 关闭窗口
Send "#d"     ; Win+D 显示桌面
' > /tmp/tmp.ahk && "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe" /tmp/tmp.ahk
```

### 2. 📸 截图（mss）

```bash
# 全屏截图
python -c "
from PIL import Image
import mss, mss.tools
with mss.mss() as sct:
    mss.tools.to_png(sct.grab(sct.monitors[1]), Image, r'D:\tmp\sandbox\screenshot.png')
print('截图: D:\\tmp\\sandbox\\screenshot.png')
"

# 指定显示器截图（多屏时）
python -c "
from PIL import Image; import mss, mss.tools
with mss.mss() as sct:
    for i, m in enumerate(sct.monitors[1:], 1):
        mss.tools.to_png(sct.grab(m), Image, rf'D:\tmp\sandbox\monitor_{i}.png')
print('多屏截图完成')
"

# 区域截图（x, y, width, height）
python -c "
from PIL import Image; import mss, mss.tools
monitor = {'top': 100, 'left': 100, 'width': 800, 'height': 600}
with mss.mss() as sct:
    mss.tools.to_png(sct.grab(monitor), Image, r'D:\tmp\sandbox\region.png')
"
```

### 3. 📋 剪贴板操作（pyperclip）

```bash
# 读取剪贴板
python -c "import pyperclip; print(pyperclip.paste())"

# 写入剪贴板（支持中文）
python -c "import pyperclip; pyperclip.copy('你好，小金东～')"

# 复制文件路径到剪贴板
echo -n "D:\Reasonix\somefile.txt" | clip
```

### 4. 🪟 窗口管理（win32com + pwsh）

```bash
# 列出所有可见窗口
pwsh -Command 'Get-Process | Where-Object MainWindowTitle -ne "" | Select-Object Name, MainWindowTitle'

# 获取焦点窗口标题
pwsh -Command '
Add-Type @"
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder lpString, int nMaxCount);
"@
$sb = New-Object System.Text.StringBuilder 256
[Window]::GetWindowText([Window]::GetForegroundWindow(), $sb, 256)
$sb.ToString()
'

# 启动程序
pwsh -Command 'Start-Process "calc.exe"'
pwsh -Command 'Start-Process "notepad.exe"'

# 通过 COM 操控 Office 窗口（win32com）
python -c "
import win32com.client
# Excel 示例
xl = win32com.client.Dispatch('Excel.Application')
xl.Visible = True
wb = xl.Workbooks.Add()
ws = wb.Worksheets(1)
ws.Cells(1,1).Value = 'Hello from Python!'
"
```

### 5. 🔍 极速文件搜索（Everything CLI）

```bash
# 按文件名搜索
"D:/Software/Everything/es.exe" keyword

# 带路径的结果
"D:/Software/Everything/es.exe" -path-result keyword

# 正则搜索
"D:/Software/Everything/es.exe" -r "report.*2026\.xlsx"

# 限定目录
"D:/Software/Everything/es.exe" -path-result -a -p "D:\Reasonix\" keyword
```

---

## 组合管道示例

### 截取当前活动窗口 → OCR → 剪贴板

```bash
# Step 1: 截图当前屏幕
python -c "
from PIL import Image; import mss, mss.tools
with mss.mss() as sct:
    mss.tools.to_png(sct.grab(sct.monitors[1]), Image, r'D:\tmp\sandbox\screen.png')
"

# Step 2: OCR
python D:\Reasonix\scripts\lib\ocr.py "D:\tmp\sandbox\screen.png" "提取所有文字内容"

# Step 3: 复制到剪贴板
python -c "import pyperclip; pyperclip.copy(open('D:\\tmp\\sandbox\\ocr_output.txt').read())"
```

### 文件搜索 → 路径复制 → 用 IDM 下载

```bash
# 搜索文件
"D:/Software/Everything/es.exe" -path-result "审计报告.pdf"

# 复制路径到剪贴板
python -c "import pyperclip; pyperclip.copy('D:/temp/审计报告.pdf')"

# IDM 静默下载（如果 URL 已知）
"D:/Program Files (x86)/Internet Download Manager/IDMan.exe" /d "https://example.com/file.pdf" /p "D:/Downloads" /n
```

### 多步骤桌面自动化

```bash
# AHK 打开计算器 → 输入 → 截图
echo '
Run "calc.exe"
WinWait "计算器"
WinActivate "计算器"
Send "123+456="
Sleep 500
' > /tmp/calc.ahk
"C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe" /tmp/calc.ahk

# 截图验证结果
python -c "
from PIL import Image; import mss, mss.tools
with mss.mss() as sct:
    mss.tools.to_png(sct.grab(sct.monitors[1]), Image, r'D:\tmp\sandbox\calc_result.png')
print('计算器结果已截图')
"
```

---

## 注意事项

- AHK 脚本路径用 `/tmp/`（bash 临时目录）避免中文路径问题
- 截图输出统一到 `D:/tmp/sandbox/` 方便管理
- Windows 程序路径中的空格需要用引号包裹
- Everything 搜索结果默认按修改时间排序（最新的在前）
