' 静默启动截图监视器（无控制台窗口）
' 由 截图监控.bat 或 Windows 启动文件夹调用

Set ws = CreateObject("Wscript.Shell")
monitor = ws.CurrentDirectory & "\scripts\lib\clipboard_monitor.py"
ws.Run "pythonw """ & monitor & """", 0, False
