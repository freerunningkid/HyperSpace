startup = CreateObject("WScript.Shell").SpecialFolders("Startup") & "\TTS-Watcher.vbs"
Set fso = CreateObject("Scripting.FileSystemObject")
fso.CopyFile "D:\Reasonix\tts-startup.vbs", startup, True
MsgBox "OK -- TTS startup installed!", 64, "TTS"
