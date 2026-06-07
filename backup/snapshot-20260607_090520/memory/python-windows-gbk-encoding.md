---
name: python-windows-gbk-encoding
title: Windows Python GBK 编码修复
description: Windows Python 控制台 GBK 编码报错修复
metadata:
  type: reference
---

**问题：** Python 在 Windows cmd/PowerShell 中 print emoji/中文报 `UnicodeEncodeError: 'gbk' codec can't encode character`  
**根因：** Windows 控制台默认 GBK 编码，Python 未主动设置 stdout 编码  
**修复方式（二选一）：**

1. **在 Python 脚本头部添加（推荐，兼容所有调用方式）：**
   ```python
   if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
       try:
           sys.stdout.reconfigure(encoding="utf-8")
       except Exception:
           pass
   ```

2. **调用时设置环境变量：**
   ```powershell
   $env:PYTHONIOENCODING='utf-8'; python script.py
   ```

**最佳实践：** 两种方式都用上。脚本内部做 reconfigure 兜底日常调用，环境变量用于 bash 管道场景。

**Why:** 本次会话中 `local_infer.py` 输出 emoji 时频繁触发此错误。
