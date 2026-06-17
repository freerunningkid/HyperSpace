"""超轻量 ZCode 监控 — 每 5 秒扫一次，有新回复写 inbox"""
import time, os, json
from pywinauto import Application

BRIDGE = r'D:\Reasonix\bridge'
INBOX = os.path.join(BRIDGE, 'inbox.txt')
STATE = os.path.join(BRIDGE, 'state.json')
STOP = os.path.join(BRIDGE, 'stop.txt')
POLL = 5

last_text = ''

while True:
    if os.path.exists(STOP):
        break
    try:
        app = Application(backend='uia').connect(title='ZCode', timeout=2)
        dlg = app.top_window()
        # Get all chat-like text
        texts = [c.window_text() for c in dlg.descendants()
                 if c.window_text() and len(c.window_text()) > 30
                 and c.element_info.control_type in ('Text', 'ListItem')]
        chats = [t for t in texts if 'ZCode' not in t and 'deepseek' not in t and '上下文' not in t]
        latest = chats[-1] if chats else ''
        
        if latest and latest != last_text:
            with open(INBOX, 'w', encoding='utf-8') as f:
                f.write(latest)
            last_text = latest
    except:
        pass
    time.sleep(POLL)
