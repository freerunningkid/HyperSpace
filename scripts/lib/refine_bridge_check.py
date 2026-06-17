import json, os
from pywinauto import Application

BRIDGE = r'D:\Reasonix\bridge'

app = Application(backend='uia').connect(title='ZCode', timeout=3)
dlg = app.top_window()

# Get ALL texts with their control types
items = []
for ctrl in dlg.descendants():
    t = ctrl.window_text()
    ct = ctrl.element_info.control_type
    if t and len(t.strip()) > 5 and ct != 'Button':
        items.append((ct, t))

# Print latest 25
print(f'Total text items: {len(items)}')
for ct, t in items[-25:]:
    print(f'  [{ct}] {t[:120]}')

# Find chat messages: texts that look like conversation content
chats = [t for ct, t in items if len(t) > 30 and 'ZCode' not in t and '连接使用' not in t 
         and '上下文' not in t and 'deepseek' not in t and '完全访问' not in t
         and '切换' not in t and '资源管理器' not in t and '工作区' not in t]
         
print(f'\nChat messages found: {len(chats)}')
for i, c in enumerate(chats[-5:]):
    print(f'  [{i}] {c[:200]}')
