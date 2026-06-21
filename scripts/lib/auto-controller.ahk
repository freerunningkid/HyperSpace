; ============================================================
; auto-controller.ahk - 桌面自动化全局热键服务
; ============================================================
; 快捷键：Ctrl+Shift+Z / Win+H / Win+Shift+T
; ============================================================
; 来源：ZCode auto-controller → Reasonix 共享工具库

#Requires AutoHotkey v2.0
#SingleInstance Force
#NoTrayIcon
#UseHook

; ---------- 配置 ----------
PYTHON_CMD := "python"
BRIDGE_SCRIPT := A_ScriptDir "\desktop_bridge.py"
LOG_FILE := A_ScriptDir "\ahk.log"

; ---------- 初始化 ----------
Log("服务启动")

; ---------- 全局热键 ----------
^+z::OnCommand()  ; Ctrl+Shift+Z → 桌面自动化菜单

; Win+H → Ctrl+` （用 SendInput 确保发送）
#h::SendInput "^``"

; Win+Shift+T → Ctrl+T （用 SendInput 确保发送）
#+t::SendInput "^t"

; ---------- 主循环 ----------
return

; ============================================================
; 函数定义
; ============================================================

OnCommand() {
    Log("热键触发")
    userInput := InputBox("请输入你的指令：", "桌面自动化指令")
    if (userInput.Result && userInput.Value != "") {
        Log("收到指令: " userInput.Value)
        Try {
            paramFile := A_Temp "\zcode_param.txt"
            FileAppend(userInput.Value, paramFile)
            result := RunAndWait('"' PYTHON_CMD '" "' BRIDGE_SCRIPT '" --param-file "' paramFile '"')
            FileDelete(paramFile)
            MsgBox("执行结果：`n`n" result, "桌面自动化", 4096)
        } Catch as err {
            MsgBox("后端执行失败：" err.Message, "桌面自动化", 4096)
        }
    }
}

RunAndWait(cmd) {
    tmpFile := A_Temp "\zcode_result.txt"
    fullCmd := cmd ' > "' tmpFile '" 2>&1'
    RunWait(A_ComSpec ' /c ' fullCmd, , "Hide")
    if FileExist(tmpFile) {
        result := Trim(FileRead(tmpFile), " `t`n`r")
        FileDelete(tmpFile)
        return result
    }
    return "(无输出)"
}

Log(msg) {
    timestamp := FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss")
    FileAppend("[" timestamp "] " msg "`n", LOG_FILE)
}
