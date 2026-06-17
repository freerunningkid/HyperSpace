import time, os, json
from pywinauto import Application

BRIDGE = r'D:\Reasonix\bridge'
STOP_FILE = os.path.join(BRIDGE, 'stop.txt')
INBOX = os.path.join(BRIDGE, 'inbox.txt')
STATE = os.path.join(BRIDGE, 'state.json')

def get_latest_reply():
    """Return the latest assistant text & message count"""
    try:
        app = Application(backend='uia').connect(title='ZCode', timeout=3)
        dlg = app.top_window()
        
        # Find all Text controls with substantive content (>20 chars)
        texts = []
        for ctrl in dlg.descendants():
            t = ctrl.window_text()
            if t and len(t) > 20 and 'ZCode' not in t:
                texts.append(t)
        
        total_msgs = len(texts)
        latest = texts[-1] if texts else ''
        return latest, total_msgs
    except Exception as e:
        return f'[err: {e}]', 0

def load_state():
    try:
        return json.load(open(STATE, 'r'))
    except:
        return {'last_text': '', 'round': 0, 'last_count': 0}

def save_state(s):
    json.dump(s, open(STATE, 'w'))

# Poll once
state = load_state()
latest, count = get_latest_reply()

if count > state.get('last_count', 0) and latest != state.get('last_text', ''):
    # New message detected
    open(INBOX, 'w', encoding='utf-8').write(latest)
    state['last_text'] = latest
    state['last_count'] = count
    state['round'] += 1
    save_state(state)
    print(f'NEW: {latest[:100]}')
else:
    print(f'No new message (count: {count}/{state.get("last_count",0)})')
