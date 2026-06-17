"""读取 ZCode 全部文本块，只输出最后的200行"""
import sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pywinauto import Application

def get_all():
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    results = []
    for ctrl in dlg.descendants():
        try:
            txt = ctrl.window_text()
        except:
            continue
        if txt and len(txt) > 3 and 'ZCode' not in txt and 'deepseek' not in txt and 'glm' not in txt and 'nohtc113' not in txt and 'Agent-ZCode' not in txt and 'ZCodeProject' not in txt:
            results.append(txt)
    return results

if __name__ == '__main__':
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    time.sleep(wait)
    texts = get_all()
    for i, t in enumerate(texts[-100:]):
        print(f'[{len(texts)-100+i}] {t[:300]}')
