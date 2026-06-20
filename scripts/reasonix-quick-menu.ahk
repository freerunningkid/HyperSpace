; ============================================================================
; Reasonix Quick Menu — 系统托盘快捷菜单
; 功能：一键启动 Reasonix / 截屏 / 打开工作区 / TTS 测试
; 作者：2B小姐姐 for 小金东
; 安装：双击运行即可，托盘图标 ⚙️
; ============================================================================

#Requires AutoHotkey v2.0
#SingleInstance Force
SetBatchLines -1

; --- 配置 ---
REASONIX_WORKSPACE := "D:\Reasonix"
SPEAK_SCRIPT := "D:\Reasonix\scripts\lib\speak.py"
SCREENSHOT_DIR := "D:\Reasonix\截图"

; --- 托盘菜单 ---
Menu Tray, DeleteAll
hMenu := Menu()
hMenu.Add("💬 启动 Reasonix", StartReasonix)
hMenu.Add("📸 截屏 + OCR", ScreenshotOCR)
hMenu.Add("📂 打开工作区", OpenWorkspace)
hMenu.Add("🔊 测试 TTS", TestTTS)
hMenu.Add("---")
hMenu.Add("📁 打开 scripts", OpenScripts)
hMenu.Add("📁 打开 .reasonix", OpenSkills)
hMenu.Add("---")
hMenu.Add("❓ 帮助", ShowHelp)
hMenu.Add("退出", ExitApp)

TraySetIcon(hMenu.IconPath)
TrayMenu := Tray.GetMenu()
TrayMenu.DeleteAll()
TrayMenu.Append(hMenu)
TraySetClick("Icon Click", "DoubleClick Click")

; --- 回调函数 ---
StartReasonix(*) {
    Run `cmd /c "cd /d """ . REASONIX_WORKSPACE . """ && reasonix"`
    TrayTip "正在启动 Reasonix...", 0
}

ScreenshotOCR(*) {
    if !DirExist(SCREENSHOT_DIR)
        DirCreate(SCREENSHOT_DIR)
    
    timestamp := FormatDateTime("yyyyMMdd_HHmmss")
    screenshotPath := SCREENSHOT_DIR . "\quick_" . timestamp . ".png"
    
    ; 截屏
    RunWait `powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $b = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($b); $g.CopyFromScreen(0,0,0,0,$b.Size); $b.Save(""" . screenshotPath . """); $g.Dispose(); $b.Dispose()"`
    
    ; OCR 识别
    if FileExist(screenshotPath) {
        result := RunWait(`python "` . SPEAK_SCRIPT . `" "截图已保存到: " . screenshotPath, &output)
        TrayTip "截图完成", screenshotPath, 3
    }
}

OpenWorkspace(*) {
    Run REASONIX_WORKSPACE
    TrayTip "打开工作区", 0
}

TestTTS(*) {
    RunWait `python "` . SPEAK_SCRIPT . `" "小金东，你好呀～ 2B小姐姐随时为你服务！"`
    TrayTip "TTS 测试", "晓晓语音已发声", 3
}

OpenScripts(*) {
    Run "D:\Reasonix\scripts"
}

OpenSkills(*) {
    Run REASONIX_WORKSPACE . "\.reasonix"
}

ShowHelp(*) {
    MsgBox "Reasonix 快捷菜单 v1.0`n`n" .
        "左键单击托盘图标: 打开菜单`n" .
        "右键单击托盘图标: 快速截屏`n" .
        "双击托盘图标: 启动 Reasonix`n`n" .
        "功能:`n" .
        "💬 启动 Reasonix 终端`n" .
        "📸 截屏 + OCR 识别`n" .
        "📂 打开工作区文件夹`n" .
        "🔊 测试 TTS 语音`n`n" .
        "提示: 右键菜单可自定义热键",
        "帮助", 0x1
}

ExitApp(*) {
    ExitApp
}

; --- 托盘右键快速截屏 ---
TrayIconClick(*) {
    ; 左键单击：显示菜单
}

DoubleClick(*) {
    ; 双击：启动 Reasonix
    StartReasonix()
}

; --- 全局热键 (可选，需安装 AHK) ---
; Ctrl+Shift+S: 快速截屏
^+s:: {
    ScreenshotOCR()
}

; Ctrl+Shift+R: 启动 Reasonix
^+r:: {
    StartReasonix()
}

; Esc: 退出程序
Esc:: {
    ExitApp
}

TrayTip "Reasonix 快捷菜单已就绪", "右键单击托盘图标使用", 2
