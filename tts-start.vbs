Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw ""D:\Reasonix\scripts\lib\tts_server.py""", 0, False
MsgBox "TTS Server started! Edge streaming → SAPI5 降级链就绪。", 64, "TTS Ready"
