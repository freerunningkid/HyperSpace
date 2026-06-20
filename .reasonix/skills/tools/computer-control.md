---
name: computer-control
description: 桌面控制：截屏/鼠标/键盘/图像定位。MCP 模式，适合需要操控本地应用的场景。
last_used: never
---
# computer-control — 桌面控制技能

> 基于 PyAutoGUI + OpenCV 的桌面自动化 MCP 服务器。
> 文件：`D:\Reasonix\scripts\mcp\computer_control_server.py`

## 能力清单

| 工具 | 功能 | 参数 |
|------|------|------|
| `screen_capture` | 截屏 | `path` (可选，保存路径) |
| `mouse_move` | 移动鼠标 | `x`, `y` |
| `mouse_click` | 单击 | `button` (left/right/middle) |
| `double_click` | 双击 | - |
| `right_click` | 右键 | - |
| `mouse_drag` | 拖拽 | `x`, `y` |
| `keyboard_type` | 输入文本 | `text` |
| `keyboard_press` | 按键 | `key` |
| `keyboard_hotkey` | 热键 | `keys` (数组) |
| `find_on_screen` | 图像定位 | `template`, `threshold` |
| `get_screen_size` | 获取屏幕尺寸 | - |
| `scroll` | 滚动 | `direction`, `clicks` |

## 典型场景

### 1. 自动化桌面操作
```
1. screen_capture → 确认当前状态
2. find_on_screen → 定位目标元素
3. mouse_move/click → 点击目标
4. keyboard_type → 输入文本
5. screen_capture → 验证结果
```

### 2. 批量文件操作
```
1. 用 os-safe MCP 操作文件
2. 用 computer-control 打开资源管理器
3. 拖拽/复制/粘贴文件
```

### 3. 应用自动化
```
1. keyboard_hotkey ["win", "r"] → 打开运行对话框
2. keyboard_type "notepad" → 输入应用名
3. keyboard_press "enter" → 启动
```

## 依赖安装

```bash
pip install Pillow pyautogui opencv-python
```

## 注意事项

- `find_on_screen` 需要模板图片，建议先用 `screen_capture` 截取目标元素
- 图像匹配阈值默认 0.8，可调低提高灵敏度
- 所有坐标基于屏幕左上角 (0, 0)
- 鼠标操作会物理移动光标，确保在安全环境下使用
