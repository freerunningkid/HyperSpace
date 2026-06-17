"""读取 ZCode Document 控件所有文本"""
import sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pywinauto import Application

def get_doc_text():
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    
    # 拿 Document 控件
    for ctrl in dlg.descendants():
        try:
            info = ctrl.element_info
            if info.control_type == 'Document':
                txt = ctrl.window_text()
                if len(txt) > 50:
                    return txt
        except:
            pass
    
    return "NO_DOC_FOUND"

if __name__ == '__main__':
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    time.sleep(wait)
    txt = get_doc_text()
    print(txt[-3000:])
