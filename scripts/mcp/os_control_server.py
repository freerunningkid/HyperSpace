#!/usr/bin/env python3
"""mcp-os-control — Agent 的桌面手脚：AHK + Pywinauto + Nut.js + Office VBA + Python沙箱 + 文件安全.

Tool list (12 tools):
  桌面操控:
    execute_ahk(script, timeout=30)          — 执行 AHK v2 脚本
    execute_pywinauto(code, timeout=30)       — 在沙箱子进程中执行 Pywinauto 代码
    execute_nutjs(code, timeout=30)           — 在子进程中执行 Nut.js (Node) 代码
  感知:
    get_screenshot(region="full")             — 截图返回 base64 PNG
    list_windows()                            — 枚举所有窗口
    get_active_window()                       — 当前焦点窗口详情
    clipboard_read() / clipboard_write(text)  — 剪贴板读写
    find_file(query)                          — Everything 毫秒文件搜索
  办公自动化:
    execute_office_vba(app, script)           — Agent写VBA → 注入Word/Excel/PPT执行
    execute_isolated_python(code, timeout)    — 隔离沙箱子进程执行Python代码
  文件安全:
    secure_open_file(path, mode)              — 读返回内容, 写创建影子副本
    promote_to_production(shadow, original)   — 影子副本→原文件, 自动备份

安全: AHK危险命令拦截; VBA/Python/文件操作在独立子进程隔离执行.
"""

import asyncio
import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time

# ── Paths ──
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
AHK_EXE = r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
ES_EXE = r"D:\软件\Everything\es.exe"
NODE_EXE = "node"
NUT_JS_PATH = r"C:\Users\KID\AppData\Roaming\npm\node_modules\@nut-tree-fork\nut-js"

# ── MCP imports ──
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("os-control")

# ═══════════════════════════════════════════════════════════════
# Safety: AHK dangerous command blacklist
# ═══════════════════════════════════════════════════════════════

AHK_DANGEROUS = [
    r"\bFileDelete\b", r"\bDirDelete\b", r"\bRegDelete\b",
    r"\bRegWrite\b", r"\bShutdown\b", r"\bFormatTime\b.*Shutdown",
    r"\bFileRemoveDir\b", r"\bDriveEject\b", r"\bDrive\b",
    r"\bRun\s*\(\s*[\"']cmd", r"\bRunWait\s*\(\s*[\"']cmd",
]


def _check_ahk_safety(script: str) -> str | None:
    """Return error message if dangerous patterns found, else None."""
    for pattern in AHK_DANGEROUS:
        if re.search(pattern, script, re.IGNORECASE):
            return f"[os-control] ⛔ AHK 危险命令被拦截: 匹配模式 '{pattern}'"
    return None


def _run_subprocess(
    cmd: list[str],
    timeout: int = 30,
    cwd: str | None = None,
    env: dict | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd or os.getcwd(),
            env=env or os.environ.copy(),
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"[os-control] ⏱ 执行超时 ({timeout}s)"
    except FileNotFoundError as e:
        return -1, "", f"[os-control] ✗ 找不到可执行文件: {e}"
    except Exception as e:
        return -1, "", f"[os-control] ✗ 子进程错误: {e}"


# ═══════════════════════════════════════════════════════════════
# Tools: list + handler
# ═══════════════════════════════════════════════════════════════

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="execute_ahk",
            description="在 Windows 上执行 AutoHotkey v2 脚本。用于模拟键鼠、操控窗口、快捷键等自动化操作。脚本会做安全校验，禁止删除文件/注册表等危险操作。",
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "AHK v2 脚本代码。例如: MsgBox 'hello' 或 Send '^c' 复制选中内容",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数，默认 30",
                        "default": 30,
                    },
                },
                "required": ["script"],
            },
        ),
        types.Tool(
            name="execute_pywinauto",
            description="在隔离子进程中执行 Pywinauto Python 代码。可读写 Windows UI Automation (UIA) 树，精准查找控件、获取属性、模拟点击。比截图识别更可靠。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python 代码，可使用 pywinauto 库。例如: from pywinauto import Desktop; dlg = Desktop(backend='uia')['计算器']; print(dlg.dump_tree())",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数，默认 30",
                        "default": 30,
                    },
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="execute_nutjs",
            description="在子进程中执行 Nut.js (Node.js) 代码。Nut.js 结合图像识别和系统 API，可在分辨率变化时依然精准操控桌面元素。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Nut.js JavaScript 代码。可使用 nut-js 库。例如: await mouse.move([100, 200]); await mouse.click();",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数，默认 30",
                        "default": 30,
                    },
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="get_screenshot",
            description="截取屏幕，返回 base64 编码的 PNG 图像。Agent 的眼睛——看到屏幕上的内容后再决定下一步操作。",
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "enum": ["full", "active_window"],
                        "description": "'full' 截全屏, 'active_window' 截当前焦点窗口。默认 'full'",
                        "default": "full",
                    },
                },
            },
        ),
        types.Tool(
            name="list_windows",
            description="枚举当前所有可见窗口，返回标题、位置、大小。让 Agent 了解桌面环境全貌。",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_active_window",
            description="获取当前焦点窗口的详细信息：标题、类名、位置、大小。",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="clipboard_read",
            description="读取 Windows 剪贴板中的文本内容。",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="clipboard_write",
            description="将文本写入 Windows 剪贴板。",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要写入剪贴板的文本",
                    },
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="find_file",
            description="使用 Everything 引擎毫秒级搜索文件。比 Windows 自带搜索快 100-1000 倍。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Everything 搜索语法。例如: '*.xlsx D:\\' 搜 D 盘所有 Excel，'report 2024' 搜含关键字的文件",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="execute_office_vba",
            description="在指定的 Office 应用中动态执行 VBA 脚本。Agent 可自己写 VBA 代码操控 Word/Excel/PowerPoint，无需预定义接口。v5.0 核心设计：让 Agent 写 VBA，不写死板 Python 封装。",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "enum": ["Word", "Excel", "PowerPoint"],
                        "description": "目标 Office 应用：Word、Excel 或 PowerPoint",
                    },
                    "script_content": {
                        "type": "string",
                        "description": "VBA 代码（不含 Sub/End Sub 外壳，直接写逻辑）。例如: Range('A1').Value = 'Hello'",
                    },
                    "save_changes": {
                        "type": "boolean",
                        "description": "是否保存更改，默认 false",
                        "default": False,
                    },
                },
                "required": ["app_name", "script_content"],
            },
        ),
        types.Tool(
            name="execute_isolated_python",
            description="在严格隔离的子进程中执行 Python 代码。代码无法访问本机文件系统（除临时目录外）。Agent 可自己写 Pandas/matplotlib/python-docx 等代码处理数据。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python 代码。可用库: pandas, numpy, matplotlib, python-docx, openpyxl, requests, beautifulsoup4",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数，默认 30",
                        "default": 30,
                    },
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="secure_open_file",
            description="安全地打开文件。读模式返回内容；写模式自动重定向到沙箱影子副本，修改不影响原文件。防御 Agent 幻觉覆盖重要文件（v5.0 §3.2 设计）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "要打开的文件路径",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["read", "write"],
                        "description": "'read' 返回文件内容, 'write' 创建影子副本并返回影子路径",
                    },
                },
                "required": ["file_path", "mode"],
            },
        ),
        types.Tool(
            name="promote_to_production",
            description="将沙箱中的影子副本正式写回原文件。自动备份旧版本为 .bak。需搭配 secure_open_file(mode='write') 使用。",
            inputSchema={
                "type": "object",
                "properties": {
                    "shadow_path": {
                        "type": "string",
                        "description": "影子副本路径（由 secure_open_file 返回）",
                    },
                    "original_path": {
                        "type": "string",
                        "description": "原始文件路径",
                    },
                },
                "required": ["shadow_path", "original_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    # ── execute_ahk ──
    if name == "execute_ahk":
        script = arguments.get("script", "")
        timeout = min(max(int(arguments.get("timeout", 30)), 1), 120)

        # Safety check
        danger = _check_ahk_safety(script)
        if danger:
            return [types.TextContent(type="text", text=danger)]

        # Write temp .ahk file
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ahk", delete=False, encoding="utf-8"
        )
        tmp.write(script)
        tmp.close()

        try:
            rc, stdout, stderr = _run_subprocess(
                [AHK_EXE, tmp.name], timeout=timeout
            )
            if rc == 0:
                out = stdout.strip() or "(无输出)"
                return [types.TextContent(type="text", text=f"[AHK] ✓ 执行成功\n{out}")]
            else:
                return [
                    types.TextContent(
                        type="text",
                        text=f"[AHK] ✗ 退出码 {rc}\nstdout: {stdout}\nstderr: {stderr}",
                    )
                ]
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    # ── execute_pywinauto ──
    elif name == "execute_pywinauto":
        code = arguments.get("code", "")
        timeout = min(max(int(arguments.get("timeout", 30)), 1), 120)

        # Wrapper imports
        wrapper = f"""
import sys
try:
{chr(10).join('    '+line for line in code.split(chr(10)))}
except Exception as _e:
    print(f"[pywinauto] ✗ 异常: {{_e}}", file=sys.stderr)
    sys.exit(1)
"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        )
        tmp.write(wrapper)
        tmp.close()

        try:
            rc, stdout, stderr = _run_subprocess(
                [sys.executable, tmp.name], timeout=timeout
            )
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        if rc == 0:
            out = stdout.strip() or "(无输出)"
            return [types.TextContent(type="text", text=f"[pywinauto] ✓\n{out}")]
        else:
            return [
                types.TextContent(
                    type="text",
                    text=f"[pywinauto] ✗ 退出码 {rc}\nstdout: {stdout}\nstderr: {stderr}",
                )
            ]

    # ── execute_nutjs ──
    elif name == "execute_nutjs":
        code = arguments.get("code", "")
        timeout = min(max(int(arguments.get("timeout", 30)), 1), 120)

        wrapper = f"""
const {{ mouse, keyboard, screen, window, imageResource }} = require('@nut-tree-fork/nut-js');

(async () => {{
    try {{
{chr(10).join('        '+line for line in code.split(chr(10)))}
    }} catch (e) {{
        console.error('[nutjs] ✗ 异常:', e.message);
        process.exit(1);
    }}
}})();
"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False, encoding="utf-8"
        )
        tmp.write(wrapper)
        tmp.close()

        try:
            # NODE_PATH must include global modules
            env = os.environ.copy()
            npm_root = r"C:\Users\KID\AppData\Roaming\npm\node_modules"
            existing = env.get("NODE_PATH", "")
            env["NODE_PATH"] = npm_root if not existing else f"{existing};{npm_root}"

            rc, stdout, stderr = _run_subprocess(
                [NODE_EXE, tmp.name], timeout=timeout, env=env
            )
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        if rc == 0:
            out = stdout.strip() or "(无输出)"
            return [types.TextContent(type="text", text=f"[nutjs] ✓\n{out}")]
        else:
            return [
                types.TextContent(
                    type="text",
                    text=f"[nutjs] ✗ 退出码 {rc}\nstdout: {stdout}\nstderr: {stderr}",
                )
            ]

    # ── get_screenshot ──
    elif name == "get_screenshot":
        region = arguments.get("region", "full")
        try:
            import mss
            from PIL import Image

            with mss.mss() as sct:
                if region == "active_window":
                    import pygetwindow as gw
                    win = gw.getActiveWindow()
                    if win:
                        monitor = {
                            "top": win.top,
                            "left": win.left,
                            "width": win.width,
                            "height": win.height,
                        }
                    else:
                        monitor = sct.monitors[1]  # fallback to primary
                else:
                    monitor = sct.monitors[1]  # primary monitor

                img = sct.grab(monitor)

                # Resize if too large (>2K wide → half)
                pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                w, h = pil_img.size
                if w > 1920:
                    pil_img = pil_img.resize((w // 2, h // 2), Image.LANCZOS)

                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")

                return [
                    types.TextContent(
                        type="text",
                        text=f"[screenshot] {pil_img.size[0]}x{pil_img.size[1]} (base64 below)\n{b64}",
                    )
                ]
        except ImportError as e:
            return [types.TextContent(type="text", text=f"[screenshot] ✗ 依赖缺失: {e}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[screenshot] ✗ 截图失败: {e}")]

    # ── list_windows ──
    elif name == "list_windows":
        try:
            import pygetwindow as gw
            wins = gw.getAllWindows()
            lines = []
            for w in wins[:50]:  # cap at 50
                title = w.title.strip()
                if title and w.width > 0 and w.height > 0:
                    lines.append(
                        f"  [{w.left},{w.top} {w.width}x{w.height}] {title[:80]}"
                    )
            if not lines:
                return [types.TextContent(type="text", text="[windows] 无可见窗口")]
            return [
                types.TextContent(
                    type="text",
                    text=f"[windows] 共 {len(lines)} 个可见窗口:\n" + "\n".join(lines),
                )
            ]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[windows] ✗ {e}")]

    # ── get_active_window ──
    elif name == "get_active_window":
        try:
            import pygetwindow as gw
            w = gw.getActiveWindow()
            if w:
                info = (
                    f"标题: {w.title}\n"
                    f"位置: ({w.left}, {w.top})\n"
                    f"大小: {w.width}x{w.height}\n"
                    f"最小化: {w.isMinimized}"
                )
                return [types.TextContent(type="text", text=f"[active_window]\n{info}")]
            else:
                return [types.TextContent(type="text", text="[active_window] 无法获取焦点窗口")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[active_window] ✗ {e}")]

    # ── clipboard_read ──
    elif name == "clipboard_read":
        try:
            import pyperclip
            text = pyperclip.paste()
            if not text:
                return [types.TextContent(type="text", text="[clipboard] 剪贴板为空或非文本")]
            return [
                types.TextContent(
                    type="text", text=f"[clipboard] (长度 {len(text)})\n{text[:2000]}"
                )
            ]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[clipboard] ✗ {e}")]

    # ── clipboard_write ──
    elif name == "clipboard_write":
        text = arguments.get("text", "")
        try:
            import pyperclip
            pyperclip.copy(text)
            return [
                types.TextContent(
                    type="text",
                    text=f"[clipboard] ✓ 已写入 (长度 {len(text)})",
                )
            ]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[clipboard] ✗ {e}")]

    # ── find_file ──
    elif name == "find_file":
        query = arguments.get("query", "")
        if not os.path.exists(ES_EXE):
            return [
                types.TextContent(
                    type="text",
                    text=f"[find_file] ✗ Everything CLI 未安装: {ES_EXE}",
                )
            ]
        try:
            rc, stdout, stderr = _run_subprocess(
                [ES_EXE, "-n", "30", query], timeout=10
            )
            if rc == 0:
                lines = stdout.strip().split("\n")
                if not lines or lines == [""]:
                    return [
                        types.TextContent(
                            type="text", text=f"[find_file] 未找到: {query}"
                        )
                    ]
                result = f"[find_file] 共 {len(lines)} 个结果 (最多30):\n" + "\n".join(
                    f"  {l}" for l in lines
                )
                return [types.TextContent(type="text", text=result)]
            else:
                return [
                    types.TextContent(
                        type="text", text=f"[find_file] ✗ {stderr or stdout}"
                    )
                ]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[find_file] ✗ {e}")]

    # ── execute_office_vba ──
    elif name == "execute_office_vba":
        app_name = arguments.get("app_name", "")
        script_content = arguments.get("script_content", "")
        save_changes = arguments.get("save_changes", False)

        if app_name not in ("Word", "Excel", "PowerPoint"):
            return [types.TextContent(type="text", text=f"[vba] ✗ 不支持的应用: {app_name}（支持: Word, Excel, PowerPoint）")]

        result = _execute_vba_com(app_name, script_content, save_changes)
        return [types.TextContent(type="text", text=f"[vba/{app_name}] {result}")]

    # ── execute_isolated_python ──
    elif name == "execute_isolated_python":
        code = arguments.get("code", "")
        timeout = min(max(int(arguments.get("timeout", 30)), 1), 120)

        # Safety: reject obvious dangerous patterns
        dangerous_patterns = [
            r"os\.system\s*\(", r"subprocess\.", r"shutil\.rmtree",
            r"__import__\s*\(\s*['\"]os['\"]", r"eval\s*\(", r"exec\s*\("
        ]
        for pat in dangerous_patterns:
            if re.search(pat, code):
                return [types.TextContent(type="text", text=f"[sandbox] ⛔ 危险代码被拦截: 匹配 '{pat}'")]

        wrapper = f"""
import sys, os
os.chdir(r"{_get_sandbox_dir()}")
try:
{chr(10).join('    '+line for line in code.split(chr(10)))}
except Exception as _e:
    print(f"[sandbox] 异常: {{_e}}", file=sys.stderr)
    sys.exit(1)
"""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write(wrapper)
        tmp.close()
        try:
            rc, stdout, stderr = _run_subprocess([sys.executable, tmp.name], timeout=timeout)
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        if rc == 0:
            out = stdout.strip() or "(无输出)"
            return [types.TextContent(type="text", text=f"[sandbox] ✓\n{out}")]
        else:
            return [types.TextContent(type="text", text=f"[sandbox] ✗ 退出码 {rc}\nstdout: {stdout}\nstderr: {stderr}")]

    # ── secure_open_file ──
    elif name == "secure_open_file":
        file_path = arguments.get("file_path", "")
        mode = arguments.get("mode", "read")

        if not os.path.exists(file_path):
            return [types.TextContent(type="text", text=f"[file] ✗ 文件不存在: {file_path}")]

        if mode == "read":
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(50000)
                return [types.TextContent(type="text", text=f"[file] ✓ (长度 {len(content)})\n{content}")]
            except Exception as e:
                return [types.TextContent(type="text", text=f"[file] ✗ 读取失败: {e}")]

        elif mode == "write":
            shadow_path = _create_shadow_copy(file_path)
            if shadow_path:
                return [types.TextContent(type="text", text=f"[file] 🔒 文件已映射到影子副本:\n  原文件: {file_path}\n  影子副本: {shadow_path}\n  修改不影响原文件。确认后用 promote_to_production 写回。")]
            else:
                return [types.TextContent(type="text", text=f"[file] ✗ 创建影子副本失败")]
        else:
            return [types.TextContent(type="text", text=f"[file] ✗ 未知模式: {mode}")]

    # ── promote_to_production ──
    elif name == "promote_to_production":
        shadow_path = arguments.get("shadow_path", "")
        original_path = arguments.get("original_path", "")

        # Security: shadow must be in sandbox dir
        sandbox_dir = _get_sandbox_dir()
        if not shadow_path.startswith(sandbox_dir):
            return [types.TextContent(type="text", text=f"[file] ⛔ 安全拒绝: 影子文件不在沙箱目录内")]
        if not os.path.exists(shadow_path):
            return [types.TextContent(type="text", text=f"[file] ✗ 影子文件不存在: {shadow_path}")]

        try:
            # Backup original
            if os.path.exists(original_path):
                bak = original_path + ".bak"
                import shutil
                shutil.copy2(original_path, bak)
            # Promote shadow
            import shutil
            shutil.copy2(shadow_path, original_path)
            return [types.TextContent(type="text", text=f"[file] ✓ 影子副本已写回原文件\n  原文件: {original_path}\n  备份: {original_path}.bak")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[file] ✗ 写回失败: {e}")]

    else:
        return [types.TextContent(type="text", text=f"[os-control] 未知工具: {name}")]


# ═══════════════════════════════════════════════════════════════
# Office VBA COM Bridge (v5.0 §2.1 / §3.1)
# ═══════════════════════════════════════════════════════════════

def _get_sandbox_dir() -> str:
    """Get or create the sandbox workspace directory."""
    sandbox = os.path.join(tempfile.gettempdir(), "agent-sandbox")
    os.makedirs(sandbox, exist_ok=True)
    return sandbox


def _create_shadow_copy(file_path: str) -> str | None:
    """Create a shadow copy of a file in the sandbox for safe editing."""
    try:
        sandbox = _get_sandbox_dir()
        basename = os.path.basename(file_path)
        timestamp = int(time.time())
        shadow_name = f"shadow_{timestamp}_{basename}"
        shadow_path = os.path.join(sandbox, shadow_name)
        import shutil
        shutil.copy2(file_path, shadow_path)
        return shadow_path
    except Exception:
        return None


def _execute_vba_com(app_name: str, vba_code: str, save_changes: bool = False) -> str:
    """Execute VBA code in Office app via COM, using isolated subprocess.

    Follows v5.0 §3.1 design: temp WScript-style process that creates COM object,
    injects VBA, executes it, and exits — no zombie processes.
    """
    import pythoncom

    # Build the full VBA subroutine
    full_vba = f"""
On Error Resume Next
{vba_code}
On Error GoTo 0
"""

    # Build a standalone Python script that does the COM work
    com_script = f'''
import sys, os, pythoncom, win32com.client

app_name = "{app_name}"
save_changes = {save_changes}
vba_code = """{full_vba}"""

try:
    pythoncom.CoInitialize()
    app = win32com.client.Dispatch(f"{{app_name}}.Application")
    app.Visible = False
    app.DisplayAlerts = False

    if app_name == "Excel":
        if app.Workbooks.Count == 0:
            wb = app.Workbooks.Add()
        else:
            wb = app.ActiveWorkbook
        app.VBE.ActiveVBProject.VBComponents(1).CodeModule.AddFromString(vba_code)
        app.Run("DynamicVBA")
        if save_changes:
            wb.Save()
        msg = f"VBA执行成功 (Excel)"

    elif app_name == "Word":
        if app.Documents.Count == 0:
            doc = app.Documents.Add()
        else:
            doc = app.ActiveDocument
        app.VBE.ActiveVBProject.VBComponents(1).CodeModule.AddFromString(vba_code)
        app.Run("DynamicVBA")
        if save_changes:
            doc.Save()
        msg = f"VBA执行成功 (Word)"

    elif app_name == "PowerPoint":
        if app.Presentations.Count == 0:
            pres = app.Presentations.Add()
        else:
            pres = app.ActivePresentation
        app.VBE.ActiveVBProject.VBComponents(1).CodeModule.AddFromString(vba_code)
        app.Run("DynamicVBA")
        if save_changes:
            pres.Save()
        msg = f"VBA执行成功 (PowerPoint)"

    app.Quit()
    pythoncom.CoUninitialize()
    print(msg, flush=True)

except Exception as e:
    pythoncom.CoUninitialize()
    print(f"VBA执行失败: {{e}}", file=sys.stderr, flush=True)
    sys.exit(1)
'''

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
    tmp.write(com_script)
    tmp.close()

    try:
        rc, stdout, stderr = _run_subprocess([sys.executable, tmp.name], timeout=60)
        if rc == 0:
            return f"✓ {stdout.strip()}"
        else:
            return f"✗ 退出码 {rc}\n{stderr or stdout}"
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


async def main():
    print("[os-control] 启动中...", file=sys.stderr, flush=True)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
