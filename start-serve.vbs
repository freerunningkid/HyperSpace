Set WshShell = CreateObject("WScript.Shell")
' 启动代理看门狗（内部自动启动 reasonix serve + 代理 + 崩溃自动恢复）
WshShell.Run "pythonw ""D:\Reasonix\scripts\lib\watchdog-proxy.py""", 0, False
