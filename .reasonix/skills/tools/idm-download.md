---
name: idm-download
description: 使用本地 IDM 后台静默下载文件，无弹窗、无键鼠模拟，纯命令行驱动
last_used: 2026-06-04
---
# IDM 后台下载 Skill

## 触发条件
用户要求下载任何文件/软件/资料时，优先使用此 Skill 而非浏览器下载或 curl/wget。

## IDM 路径
```
D:\软件\Internet Download Manager\IDM\IDMan.exe
```

## 命令行语法

```
IDMan.exe /d <URL> [/n] [/s] [/p <save_path>] [/f <filename>]
```

| 参数 | 作用 |
|------|------|
| `/d URL` | 添加下载任务（必需） |
| `/n` | **静默模式**：不弹出"添加下载"对话框，直接使用默认设置 |
| `/s` | ⚠ 启动整个下载队列（非单个任务），已弃用 — 改用 IDM 自动调度 |
| `/p path` | 指定保存目录（可选，默认 IDM 下载文件夹） |
| `/f name` | 指定保存文件名（可选，默认从 URL 提取） |
| `/a` | 仅添加到队列，不立即开始 |

## 执行流程

### Step 0: 去重检查
- 检查在当前会话中是否已经为同一 URL 提交过 IDM 任务
- 已提交过 → **跳过**，告知用户"该下载已在 IDM 队列中"
- 未提交过 → 记录 URL 到会话内存后继续

### Step 1: 获取准确的下载链接
- 从网页/API 响应中提取 **直接下载链接**（非页面链接）
- GitHub Release 资源链接格式：`https://github.com/<owner>/<repo>/releases/download/<tag>/<filename>`
- 必须确保是 **直链**，不是 HTML 页面

### Step 2: 确定保存路径
- 软件/工具 → `D:\临时\`
- 其他资料 → 询问用户，默认 `D:\临时\`

### Step 3: 构造命令
```cmd
"D:\软件\Internet Download Manager\IDM\IDMan.exe" /d "<直链URL>" /n /p "<保存目录>"
```

### Step 4: 执行
- 使用 `cmd.exe /c` 包裹执行（路径含中文，bash 直调会失败）
- 命令会立即返回（IDM 后台接管下载），无需等待

### Step 5: 确认
- 告知用户："已交给 IDM 后台下载 → 保存到 `<路径>`"
- 不再轮询下载进度（IDM 有自己的完成提示）
- 如果是软件安装包，下载完成后提醒用户安装路径

## 注意事项
- `/n` 静默模式在部分旧版 IDM 可能不生效，如果弹出对话框让用户手动点"开始下载"也无妨
- 如果 IDM 未运行，`IDMan.exe /d` 会自动启动 IDM 主程序
- 不要在 `bash(run_in_background=true)` 中执行，用 `cmd.exe /c` 包裹执行即可（路径含中文时 bash 直调失败）
- **绝不使用键鼠模拟、SendKeys、AutoHotkey 等方式**——命令行 `/n` 参数就是为静默设计的
- **禁止使用 `/s` 参数**：`/s` 会启动**整个下载队列**中的所有待下载任务，而不仅是刚添加的任务，是重复下载的根因。IDM 有内置调度器，`/d` 添加后会自动开始下载，无需额外触发
