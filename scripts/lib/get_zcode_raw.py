"""读取 ZCode 最新消息的纯文本"""
import sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pywinauto import Application

def get_raw_texts():
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    results = []
    for ctrl in dlg.descendants():
        try:
            txt = ctrl.window_text()
        except:
            continue
        if txt and len(txt) > 3 and 'glm' not in txt and 'deepseek' not in txt and 'ZCodeProject' not in txt and 'Agent-ZCode' not in txt and 'nohtc113' not in txt and 'ZCode' not in txt:
            results.append(txt)
    return results

if __name__ == '__main__':
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    time.sleep(wait)
    texts = get_raw_texts()
    # Find messages near the end
    for i, t in enumerate(texts[-30:]):
        idx = len(texts) - 30 + i
        print(f'[{idx}] {t[:200]}')
