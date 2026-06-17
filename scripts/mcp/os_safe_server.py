#!/usr/bin/env python3
"""os-safe MCP — 精简安全套件：AHK + Office VBA + 文件影子副本.

保留 os-control 中需要隔离/安全校验的 4 核心工具。
轻量操作用 CLI 技能（clipboard/window/es/screenshot/python/nutjs/pywinauto）。

Tool list (4 tools):
  execute_ahk(script, timeout=30)          — AHK v2 脚本（含危险命令拦截）
  execute_office_vba(app, script, save)    — Agent 写 VBA → COM 隔离执行
  secure_open_file(path, mode)             — 读返回内容, 写创建影子副本
  promote_to_production(shadow, original)  — 影子副本→原文件, 自动备份
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time

# ── Paths ──
AHK_EXE = r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"

# ── MCP imports ──
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("os-safe")

# ═══════════════════════════════════════════════════════════════
# Safety
# ═══════════════════════════════════════════════════════════════

AHK_DANGEROUS = [
    r"\bFileDelete\b", r"\bDirDelete\b", r"\bRegDelete\b",
    r"\bRegWrite\b", r"\bShutdown\b", r"\bFormatTime\b.*Shutdown",
    r"\bFileRemoveDir\b", r"\bDriveEject\b", r"\bDrive\b",
    r"\bRun\s*\(\s*[\"']cmd", r"\bRunWait\s*\(\s*[\"']cmd",
]

SANDBOX_DIR = os.path.join(tempfile.gettempdir(), "agent-sandbox")


def _check_ahk_safety(script: str) -> str | None:
    for pattern in AHK_DANGEROUS:
        if re.search(pattern, script, re.IGNORECASE):
            return f"[os-safe] ⛔ AHK 危险命令被拦截: '{pattern}'"
    return None


def _run_subprocess(cmd: list[str], timeout=30) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"[os-safe] ⏱ 超时 ({timeout}s)"
    except Exception as e:
        return -1, "", f"[os-safe] ✗ {e}"


def _get_sandbox_dir() -> str:
    os.makedirs(SANDBOX_DIR, exist_ok=True)
    return SANDBOX_DIR


def _create_shadow_copy(file_path: str) -> str | None:
    try:
        import shutil
        sandbox = _get_sandbox_dir()
        basename = os.path.basename(file_path)
        shadow = os.path.join(sandbox, f"shadow_{int(time.time())}_{basename}")
        shutil.copy2(file_path, shadow)
        return shadow
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# Tools
# ═══════════════════════════════════════════════════════════════

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="execute_ahk",
            description="执行 AutoHotkey v2 脚本，安全校验拦截危险命令",
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {"type": "string"},
                    "timeout": {"type": "integer", "default": 30},
                },
                "required": ["script"],
            },
        ),
        types.Tool(
            name="execute_office_vba",
            description="在 Office 应用中执行 VBA 脚本（Word/Excel/PowerPoint）",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "enum": ["Word", "Excel", "PowerPoint"]},
                    "script_content": {"type": "string"},
                    "save_changes": {"type": "boolean", "default": False},
                },
                "required": ["app_name", "script_content"],
            },
        ),
        types.Tool(
            name="secure_open_file",
            description="安全文件打开：读模式返回内容，写模式创建隔离影子副本",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "mode": {"type": "string", "enum": ["read", "write"]},
                },
                "required": ["file_path", "mode"],
            },
        ),
        types.Tool(
            name="promote_to_production",
            description="将影子副本写回原文件，自动备份为 .bak",
            inputSchema={
                "type": "object",
                "properties": {
                    "shadow_path": {"type": "string"},
                    "original_path": {"type": "string"},
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

        danger = _check_ahk_safety(script)
        if danger:
            return [types.TextContent(type="text", text=danger)]

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".ahk", delete=False, encoding="utf-8")
        tmp.write(script)
        tmp.close()
        try:
            rc, stdout, stderr = _run_subprocess([AHK_EXE, tmp.name], timeout)
            if rc == 0:
                return [types.TextContent(type="text", text=f"[AHK] ✓\n{stdout.strip() or '(无输出)'}")]
            return [types.TextContent(type="text", text=f"[AHK] ✗ {rc}\n{stderr}")]
        finally:
            try: os.unlink(tmp.name)
            except: pass

    # ── execute_office_vba ──
    elif name == "execute_office_vba":
        app_name = arguments.get("app_name", "")
        script_content = arguments.get("script_content", "")
        save_changes = arguments.get("save_changes", False)

        if app_name not in ("Word", "Excel", "PowerPoint"):
            return [types.TextContent(type="text", text=f"[VBA] ✗ 不支持: {app_name}")]

        vba_code = f"\nOn Error Resume Next\n{script_content}\nOn Error GoTo 0\n"

        com_script = f'''
import sys, os, pythoncom, win32com.client
app_name = "{app_name}"
save = {str(save_changes).lower()}
vba = """{vba_code}"""
try:
    pythoncom.CoInitialize()
    app = win32com.client.Dispatch(f"{{app_name}}.Application")
    app.Visible = False
    app.DisplayAlerts = False
    if app_name == "Excel":
        wb = app.Workbooks.Add() if app.Workbooks.Count == 0 else app.ActiveWorkbook
        app.VBE.ActiveVBProject.VBComponents(1).CodeModule.AddFromString(vba)
        app.Run("DynamicVBA")
        if save: wb.Save()
    elif app_name == "Word":
        doc = app.Documents.Add() if app.Documents.Count == 0 else app.ActiveDocument
        app.VBE.ActiveVBProject.VBComponents(1).CodeModule.AddFromString(vba)
        app.Run("DynamicVBA")
        if save: doc.Save()
    elif app_name == "PowerPoint":
        pres = app.Presentations.Add() if app.Presentations.Count == 0 else app.ActivePresentation
        app.VBE.ActiveVBProject.VBComponents(1).CodeModule.AddFromString(vba)
        app.Run("DynamicVBA")
        if save: pres.Save()
    app.Quit()
    pythoncom.CoUninitialize()
    print("VBA执行成功", flush=True)
except Exception as e:
    pythoncom.CoUninitialize()
    print(f"VBA失败: {{e}}", file=sys.stderr, flush=True)
    sys.exit(1)
'''
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write(com_script)
        tmp.close()
        try:
            rc, stdout, stderr = _run_subprocess([sys.executable, tmp.name], 60)
            if rc == 0: return [types.TextContent(type="text", text=f"[VBA/{app_name}] ✓")]
            return [types.TextContent(type="text", text=f"[VBA/{app_name}] ✗\n{stderr or stdout}")]
        finally:
            try: os.unlink(tmp.name)
            except: pass

    # ── secure_open_file ──
    elif name == "secure_open_file":
        file_path = arguments.get("file_path", "")
        mode = arguments.get("mode", "read")

        if not os.path.exists(file_path):
            return [types.TextContent(type="text", text=f"[file] ✗ 不存在: {file_path}")]

        if mode == "read":
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(50000)
                return [types.TextContent(type="text", text=f"[file] ✓ ({len(content)}B)\n{content}")]
            except Exception as e:
                return [types.TextContent(type="text", text=f"[file] ✗ {e}")]

        elif mode == "write":
            shadow = _create_shadow_copy(file_path)
            if shadow:
                return [types.TextContent(type="text", text=f"[file] 🔒 影子副本:\n  原文件: {file_path}\n  影子: {shadow}\n  确认后用 promote_to_production 写回")]
            return [types.TextContent(type="text", text="[file] ✗ 创建影子副本失败")]

    # ── promote_to_production ──
    elif name == "promote_to_production":
        shadow = arguments.get("shadow_path", "")
        original = arguments.get("original_path", "")

        if not shadow.startswith(_get_sandbox_dir()):
            return [types.TextContent(type="text", text="[file] ⛔ 影子文件不在沙箱目录")]
        if not os.path.exists(shadow):
            return [types.TextContent(type="text", text=f"[file] ✗ 影子不存在")]

        try:
            import shutil
            if os.path.exists(original):
                shutil.copy2(original, original + ".bak")
            shutil.copy2(shadow, original)
            return [types.TextContent(type="text", text=f"[file] ✓ 已写回\n  备份: {original}.bak")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[file] ✗ {e}")]

    else:
        return [types.TextContent(type="text", text=f"[os-safe] 未知工具: {name}")]


async def main():
    print("[os-safe] 启动中...", file=sys.stderr, flush=True)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
