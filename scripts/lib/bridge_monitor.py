import time, os, json, sys
from pywinauto import Application

BRIDGE = r'D:\Reasonix\bridge'
STATE = os.path.join(BRIDGE, 'state.json')
INBOX = os.path.join(BRIDGE, 'inbox.txt')
STOP = os.path.join(BRIDGE, 'stop.txt')
POLL = 5

def get_latest():
    try:
        app = Application(backend='uia').connect(title='ZCode', timeout=2)
        dlg = app.top_window()
        texts = [c.window_text() for c in dlg.descendants()
                 if c.window_text() and len(c.window_text()) > 25
                 and c.element_info.control_type in ('Text', 'ListItem')]
        chats = [t for t in texts if 'ZCode' not in t and 'deepseek' not in t and '上下文' not in t and '连接' not in t]
        return chats[-1] if chats else ''
    except:
        return ''

def check():
    state = {}
    if os.path.exists(STATE):
        try: state = json.load(open(STATE, 'r'))
        except: pass
    
    latest = get_latest()
    prev = state.get('last_text', '')
    
    if latest and latest != prev:
        with open(INBOX, 'w', encoding='utf-8') as f:
            f.write(latest)
        state['last_text'] = latest
        state['new'] = True
        print(f'[bridge] NEW: {latest[:60]}')
    else:
        state['new'] = False
    
    state['checked_at'] = time.time()
    json.dump(state, open(STATE, 'w'))
    sys.stdout.flush()

print('[bridge] Monitor started')
while True:
    if os.path.exists(STOP):
        print('[bridge] STOP signal received, exiting')
        break
    try:
        check()
    except Exception as e:
        print(f'[bridge] Error: {e}')
    time.sleep(POLL)
