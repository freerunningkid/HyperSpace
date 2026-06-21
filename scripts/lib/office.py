#!/usr/bin/env python3
"""
Office CLI — Word/Excel 自动化，替代 MCP office-vba-bridge
不依赖 MCP，直接 Python COM 调用（win32com）。

用法:
  python scripts/lib/office.py word new <path>              新建 Word 文档
  python scripts/lib/office.py word open <path> [script]   打开 Word 并执行操作
  python scripts/lib/office.py excel new <path>            新建 Excel 工作簿
  python scripts/lib/office.py excel open <path> [script]  打开 Excel 并执行操作

script 参数为 JSON 字符串，包含操作序列:
  python scripts/lib/office.py word new test.docx '[
    {"action":"write","text":"Hello World","bold":true},
    {"action":"save"}
  ]'
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def _ensure_win32com():
    """确保 win32com 可用"""
    try:
        import win32com.client
        return win32com.client
    except ImportError:
        print("[ERROR] pywin32 未安装。运行: pip install pywin32")
        sys.exit(1)


# ── Word ────────────────────────────────────────────────────


def word_new(path: str, actions: list = None):
    """新建 Word 文档"""
    win32com = _ensure_win32com()
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Add()
    _exec_word_actions(doc, actions or [])
    doc.SaveAs(os.path.abspath(path))
    doc.Close()
    word.Quit()
    return {"status": "ok", "file": os.path.abspath(path)}


def word_open(path: str, actions: list = None):
    """打开 Word 文档并执行操作"""
    win32com = _ensure_win32com()
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(os.path.abspath(path))
    _exec_word_actions(doc, actions or [])
    doc.Save()
    doc.Close()
    word.Quit()
    return {"status": "ok", "file": os.path.abspath(path)}


def _exec_word_actions(doc, actions: list):
    """执行 Word 操作序列"""
    for i, action in enumerate(actions):
        act = action.get("action", "")
        if act == "write":
            selection = doc.Application.Selection
            text = action.get("text", "")
            if action.get("bold"):
                selection.Font.Bold = True
            if action.get("font_size"):
                selection.Font.Size = action["font_size"]
            selection.TypeText(text)
            # Reset bold
            if action.get("bold"):
                selection.Font.Bold = False
        elif act == "newline":
            doc.Application.Selection.TypeParagraph()
        elif act == "heading":
            selection = doc.Application.Selection
            selection.Style = doc.Styles(f"Heading {action.get('level', 1)}")
            selection.TypeText(action.get("text", ""))
            selection.TypeParagraph()
            # Reset to normal
            selection.Style = doc.Styles("Normal")
        elif act == "save":
            doc.Save()


# ── Excel ───────────────────────────────────────────────────


def excel_new(path: str, actions: list = None):
    """新建 Excel 工作簿"""
    win32com = _ensure_win32com()
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    wb = excel.Workbooks.Add()
    _exec_excel_actions(wb, actions or [])
    wb.SaveAs(os.path.abspath(path))
    wb.Close()
    excel.Quit()
    return {"status": "ok", "file": os.path.abspath(path)}


def excel_open(path: str, actions: list = None):
    """打开 Excel 并执行操作"""
    win32com = _ensure_win32com()
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    wb = excel.Workbooks.Open(os.path.abspath(path))
    _exec_excel_actions(wb, actions or [])
    wb.Save()
    wb.Close()
    excel.Quit()
    return {"status": "ok", "file": os.path.abspath(path)}


def _exec_excel_actions(wb, actions: list):
    """执行 Excel 操作序列"""
    for action in actions:
        act = action.get("action", "")
        if act == "set":
            ws = wb.Sheets(action.get("sheet", 1))
            cell = action.get("cell", "A1")
            ws.Range(cell).Value = action.get("value", "")
        elif act == "formula":
            ws = wb.Sheets(action.get("sheet", 1))
            cell = action.get("cell", "A1")
            ws.Range(cell).Formula = action.get("formula", "")
        elif act == "pivot":
            _create_pivot(wb, action)
        elif act == "save":
            wb.Save()


def _create_pivot(wb, action: dict):
    """创建透视表"""
    try:
        from win32com.client import constants
    except ImportError:
        constants = None
    # 实际实现按需扩展
    pass


# ── CLI ─────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Office 自动化 CLI（替代 MCP）")
    parser.add_argument("app", choices=["word", "excel"], help="Office 应用")
    parser.add_argument("mode", choices=["new", "open"], help="新建/打开")
    parser.add_argument("file", help="文件路径")
    parser.add_argument("actions", nargs="?", default="[]", help='操作 JSON，如 \'[{"action":"write","text":"Hi"}]\'')

    args = parser.parse_args()

    try:
        actions = json.loads(args.actions)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON 解析失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    if args.app == "word":
        result = word_new(args.file, actions) if args.mode == "new" else word_open(args.file, actions)
    else:
        result = excel_new(args.file, actions) if args.mode == "new" else excel_open(args.file, actions)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
