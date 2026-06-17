"""探测 ZCode 窗口控件结构"""
from pywinauto import Application
import time

try:
    app = Application(backend='uia').connect(title='ZCode', timeout=3)
    dlg = app.top_window()
    print(f'Window title: {dlg.window_text()}')
    
    for ctrl in dlg.descendants():
        info = ctrl.element_info
        if info.control_type in ('Edit', 'Button', 'Document', 'ComboBox'):
            txt = ctrl.window_text()[:50] if ctrl.window_text() else ''
            print(f'  type={info.control_type:12s} name="{txt}" class={info.class_name}')
except Exception as e:
    print(f'Error: {e}')
