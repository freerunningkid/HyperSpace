"""读取 ZCode 最新回复内容"""
import sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pywinauto import Application

def read_latest_reply():
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    
    # 获取所有较长的 Text / Document text
    texts = []
    for ctrl in dlg.descendants():
        try:
            txt = ctrl.window_text()
        except:
            continue
        if txt and len(txt) > 50:
            texts.append(txt)
    
    # 取最长的几个文本（通常是最近的回复）
    texts.sort(key=len, reverse=True)
    return texts[:5]

if __name__ == '__main__':
    # 等几秒让 ZCode 生成回复
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    print(f"Waiting {wait}s for reply...")
    time.sleep(wait)
    
    replies = read_latest_reply()
    print("\n=== Latest replies ===")
    for i, r in enumerate(replies):
        print(f"\n--- Reply {i+1} (len={len(r)}) ---")
        print(r[:2000])
