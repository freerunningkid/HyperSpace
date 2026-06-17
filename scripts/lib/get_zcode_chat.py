"""读取 ZCode 聊天框完整文本"""
import sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pywinauto import Application

def get_full_chat():
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    
    # 获取 Document 控件（聊天区主容器）
    for ctrl in dlg.descendants():
        try:
            info = ctrl.element_info
            if info.control_type == 'Document':
                txt = ctrl.window_text()
                if len(txt) > 100:
                    return txt
        except:
            pass
    
    # fallback: 拿所有 Text 控件拼接
    parts = []
    for ctrl in dlg.descendants():
        try:
            info = ctrl.element_info
            if info.control_type in ('Text', 'ListItem'):
                txt = ctrl.window_text()
                if txt and len(txt) > 5 and 'ZCode' not in txt and 'deepseek' not in txt:
                    parts.append(txt)
        except:
            pass
    return '\n---\n'.join(parts[-20:])

if __name__ == '__main__':
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    print(f"Waiting {wait}s...")
    time.sleep(wait)
    
    full = get_full_chat()
    print(full[-3000:])
