"""读取 ZCode 最新回复 — 按控件层次顺序"""
import sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pywinauto import Application

def read_all_chat_text():
    app = Application(backend='uia').connect(title='ZCode', timeout=5)
    dlg = app.top_window()
    
    all_texts = []
    # Collect all Text controls with meaningful length
    for ctrl in dlg.descendants():
        try:
            info = ctrl.element_info
            if info.control_type in ('Text', 'Document', 'ListItem'):
                txt = ctrl.window_text()
                if txt and len(txt) > 10:
                    all_texts.append((info.control_type, txt[:1000]))
        except:
            pass
    
    return all_texts

if __name__ == '__main__':
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f"Waiting {wait}s...")
    time.sleep(wait)
    
    texts = read_all_chat_text()
    print(f"\n=== Found {len(texts)} text blocks ===")
    for i, (ctype, txt) in enumerate(texts):
        print(f"\n--- [{ctype}] Block {i+1} ({len(txt)} chars) ---")
        print(txt[:800])
