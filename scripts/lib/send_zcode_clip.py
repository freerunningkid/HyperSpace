"""发送消息到 ZCode — 用剪贴板粘贴 + Ctrl+Enter 方式"""
import sys, time, subprocess, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pywinauto import Application, keyboard

def send_clipboard_message(message):
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    
    # 找输入框
    edit = None
    for ctrl in dlg.descendants():
        if ctrl.element_info.control_type == 'Edit':
            txt = ctrl.window_text()
            if not txt or txt.strip() == '':
                edit = ctrl
                break
    
    if not edit:
        print("ERROR: Could not find input box")
        return False
    
    # 聚焦输入框
    edit.set_focus()
    time.sleep(0.3)
    
    # 先把消息写到剪贴板
    import win32clipboard
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(message, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    time.sleep(0.2)
    
    # Ctrl+V 粘贴
    keyboard.send_keys('^v')
    time.sleep(0.5)
    
    # 找发送按钮
    send_btn = None
    for ctrl in dlg.descendants():
        if ctrl.element_info.control_type == 'Button':
            cls = ctrl.element_info.class_name
            if 'bg-brand' in cls:
                send_btn = ctrl
                break
    
    if send_btn:
        send_btn.click_input()
        print("Sent via click")
    else:
        keyboard.send_keys('{ENTER}')
        print("Sent via Enter (fallback)")
    
    time.sleep(1)
    return True

if __name__ == '__main__':
    msg = sys.argv[1] if len(sys.argv) > 1 else '你好，测试消息'
    send_clipboard_message(msg)
