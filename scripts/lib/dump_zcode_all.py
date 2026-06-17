"""读取 ZCode 全部原始文本块"""
import sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pywinauto import Application

def get_all_raw():
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    results = []
    for ctrl in dlg.descendants():
        try:
            txt = ctrl.window_text()
        except:
            continue
        if txt and len(txt) > 2:
            results.append(txt)
    return results

if __name__ == '__main__':
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    time.sleep(wait)
    texts = get_all_raw()
    for i, t in enumerate(texts):
        print(f'[{i:4d}] ({len(t):3d}ch) {t[:300]}')
