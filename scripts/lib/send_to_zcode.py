"""发送消息到 ZCode — 用 pywinauto"""
import sys, time
from pywinauto import Application, keyboard
from pywinauto.timings import wait_until

def send_to_zcode(message):
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    
    # 找输入框 (Edit control with empty name, the chat input)
    edit = None
    for ctrl in dlg.descendants():
        if ctrl.element_info.control_type == 'Edit':
            txt = ctrl.window_text()
            # The empty-name edit is the chat input
            if not txt or txt.strip() == '':
                edit = ctrl
                break
    
    if not edit:
        print("ERROR: Could not find input box")
        return False
    
    # 聚焦输入框
    edit.set_focus()
    time.sleep(0.3)
    
    # 输入文字 — 用键盘类型模拟
    edit.type_keys(message, with_spaces=True, set_foreground=False)
    time.sleep(0.5)
    
    # 找发送按钮 — class name 含 "bg-brand" 的就是发送按钮
    send_btn = None
    for ctrl in dlg.descendants():
        if ctrl.element_info.control_type == 'Button':
            cls = ctrl.element_info.class_name
            if 'bg-brand' in cls or 'bg-brand' in str(ctrl.element_info):
                send_btn = ctrl
                break
    
    if not send_btn:
        # fallback: 用 Enter 发送
        keyboard.send_keys('{ENTER}')
        print("Sent via Enter (fallback)")
    else:
        send_btn.click_input()
        print("Sent via click")
    
    time.sleep(1)
    return True

if __name__ == '__main__':
    msg = sys.argv[1] if len(sys.argv) > 1 else '你好，测试消息'
    send_to_zcode(msg)
