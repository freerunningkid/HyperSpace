import time
from pywinauto import Application

# UIA connection to ZCode
try:
    app = Application(backend="uia").connect(title="ZCode", timeout=5)
    dlg = app.top_window()
    
    print("=== Window Info ===")
    print(f"Title: {dlg.window_text()}")
    print(f"Class: {dlg.element_info.class_name}")
    
    print("\n=== All UI Elements ===")
    ctrls = dlg.descendants()
    print(f"Total controls: {len(ctrls)}")
    
    # Find text/element controls that might contain chat
    for ctrl in ctrls:
        ctrl_type = ctrl.element_info.control_type
        text = ctrl.window_text()
        if text and len(text.strip()) > 3:
            print(f"  [{ctrl_type}] {text[:120]}")
            if len(text) > 200:
                print(f"    FULL: {text[:300]}")
                
except Exception as e:
    print(f"UIA Error: {e}")
    # Try finding by process
    import subprocess
    r = subprocess.run('tasklist /FI "IMAGENAME eq ZCode.exe" /NH', shell=True, capture_output=True, text=True)
    print(f"Process search: {r.stdout[:200]}")
