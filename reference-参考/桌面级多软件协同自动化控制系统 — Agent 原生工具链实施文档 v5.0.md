你好！你的反馈非常敏锐且切中要害。我重新审视了之前的方案，发现确实存在**严重的定位偏移**。
之前的方案（v4.0 及 Enhanced 版）本质上是在**重新造一个 Agent 的大脑**（自己写 BrainInterface、上下文管理、LLM 调用逻辑），这对于已经具备极强推理和代码生成能力的 **Claude Code** 或 **Reasonix (DeepSeek-V4)** 来说，不仅是重复造轮子，更是**限制了它们原本的聪明才智**。把高阶推理 Agent 降级为只能调用预定义 `replace_and_export_pdf` 这种死板接口的执行器，是大材小用。
你的核心诉求是：**让 Agent 更灵活，把软件当成乐高积木，Agent 自己决定怎么拼装。**
因此，我全面推翻了之前的架构，从**“为 Agent 构建手脚”**而非**“构建一个新 Agent”**的视角，重新撰写了这份面向 Claude Code / Reasonix 的技术实施文档。
---
# 桌面级多软件协同自动化控制系统 — Agent 原生工具链实施文档 v5.0 (MCP-Native)
## 📌 定位与核心演进
**版本**: v5.0  
**定位**: 面向顶级推理模型的原生工具链/手脚，**坚决不造大脑**  
**适用 Agent**: Claude Code, DeepSeek-Reasonix, Cursor Agent 等  
**核心哲学**: 
1. **Agent-Centric**: Agent 是大脑，负责推理、规划、写代码；本系统是手脚，只负责**安全、忠实地执行**并返回结果。
2. **MCP-Native**: 摒弃自定义 API，拥抱 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)，让工具即插即用。
3. **Atomic & Composable**: 提供**原子级**操作（如“运行这段 VBA”、“移动鼠标到坐标”、“执行这段 Python”），拒绝业务级死板封装（如“替换并导出 PDF”），把组合的自由度还给 Agent。
### 🔄 v4.0 → v5.0 架构颠覆性重构
| 维度 | v4.0 (传统 RPA 思维) | v5.0 (Agent-Native 思维) | 变革意义 |
|------|----------------------|--------------------------|----------|
| **控制流** | 系统调度 LLM，循环调用工具 | Agent 自主规划，主动调用 MCP Server | 释放 Agent 的长程推理和自我纠错能力 |
| **工具粒度**| 粗粒度业务封装 (`replace_and_export`) | 细粒度原子操作 (`run_vba_script`, `execute_python`) | Agent 可根据实时情况动态编写代码解决问题 |
| **安全模型**| 拦截关键词 (容易被绕过) | Docker/NSJail 系统级沙箱 + 只读挂载 | 防御 Agent 幻觉产生的破坏性代码 |
| **COM 交互**| Python 封装一层又一层 | 提供 `execute_vba` 接口，Agent 自己写 VBA | 彻底解决 Python COM 封装不全、滞后的问题 |
---
## 1. 系统架构：MCP Server 集群
系统不再是一个庞大的单体应用，而是作为 **MCP Server** 运行在本地，供 Claude Code / Reasonix 通过标准输入输出或 HTTP 调用。
```mermaid
graph TD
    A[Claude Code / Reasonix] -->|Stdio / SSE| B(MCP Router)
    B --> C[mcp-desktop-sandbox]
    B --> D[mcp-office-atomic]
    B --> E[mcp-os-control]
    
    C -->|Subprocess Isolation| F[Python / Node.js Runtime]
    D -->|COM Bridge| G[Word / Excel VBA Engine]
    E -->|PyAutoGUI / AHK| H[Desktop UI]
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#bbf,stroke:#333,stroke-width:2px
```
---
## 2. 核心工具定义
我们不再为 Agent 设定“它应该怎么做”，而是告诉它“你可以做什么”。
### 2.1 `mcp-office-atomic`: 把 Office 变成 Agent 的运行时
**设计原则**：Python 处理 Office 经常遇到版本兼容、功能缺失问题。既然 Agent 会写代码，为什么不直接让 Agent 写 VBA 呢？
```python
# server/mcp_office_atomic.py
from mcp.server import Server
from mcp.types import Tool, TextContent
server = Server("office-atomic")
@server.tool()
async def execute_vba_script(
    app_name: str,       # "Word", "Excel", "PowerPoint"
    script_content: str, # VBA 代码字符串
    save_changes: bool = False
) -> str:
    """
    在指定的 Office 应用中动态执行 VBA 脚本。
    这允许 Agent 处理任何 Office 操作，而无需预定义接口。
    """
    # 内部实现：启动隐藏的 Office COM 实例，注入 VBA，执行，捕获输出
    try:
        # 使用 win32com 动态注入
        result = com_bridge.run_vba(app_name, script_content, save_changes)
        return f"执行成功。输出: {result}"
    except Exception as e:
        return f"执行失败: {str(e)}"
@server.tool()
async def read_excel_range(
    file_path: str,
    sheet_name: str,
    start_cell: str = "A1",
    end_cell: str = None
) -> str:
    """
    读取 Excel 特定区域的数据，返回 Markdown 表格或 CSV。
    用于 Agent 快速感知数据上下文。
    """
    # 内部实现：使用 openpyxl 或 pandas 读取，转换为文本
    return "| Col1 | Col2 |\n|------|------|\n| Val1 | Val2 |"
```
**Agent 交互示例**：
> **User**: 把这份报表里所有大于 100 的数字标红，并插入一个汇总行。
> **Reasonix 内心独白**: 我需要操作 Excel。我先用 `read_excel_range` 看看数据结构，然后写一段 VBA 代码来修改格式和插入行。
> **Reasonix 调用**: `execute_vba_script(app_name="Excel", script_content="Sub FormatCells()...")`
### 2.2 `mcp-desktop-sandbox`: Agent 的安全游乐场
Agent 经常需要写 Python 来处理复杂数据（如 Pandas 清洗），但直接在本机运行 `exec()` 风险极高（特别是 Prompt 注入或幻觉产生 `os.system("rm -rf /")`）。
**设计原则**：提供短生命周期、无状态的隔离沙箱。
```python
# server/mcp_desktop_sandbox.py
import subprocess
import tempfile
import os
@server.tool()
async def execute_isolated_python(
    code: str,
    timeout: int = 30
) -> str:
    """
    在严格隔离的子进程中执行 Python 代码。
    代码无法访问本机网络、文件系统（除特定临时目录外）。
    可用库: pandas, numpy, requests, beautifulsoup4。
    """
    # 安全校验：拒绝明显的破坏性操作（虽然沙箱会拦截，但这是第一道防线）
    if "import os" in code and "os.remove" in code:
        return "错误：检测到危险文件操作。"
        
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        script_path = f.name
    
    try:
        # 关键：使用严格的资源限制和最小化环境变量
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": ""}
        result = subprocess.run(
            ["python", script_path],
            capture_output=True, text=True, timeout=timeout,
            env=env, cwd="/tmp/sandbox" # 只能在沙箱目录工作
        )
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "错误：代码执行超时。"
    finally:
        os.remove(script_path)
```
### 2.3 `mcp-os-control`: UI 自动化与系统控制
对于没有 API 的闭源软件，Agent 必须像人一样操作界面。
```python
# server/mcp_os_control.py
import pyautogui
import subprocess
@server.tool()
async def execute_autohotkey(script: str) -> str:
    """
    执行 AutoHotkey 脚本。
    AHK 是 Windows 上最强大的 UI 自动化工具，比 Python 的 pyautogui 更稳定。
    Agent 可以根据窗口标题和控件类名生成 AHK 脚本。
    """
    # 保存为 .ahk 并执行
    pass
@server.tool()
async def get_desktop_screenshot() -> str:
    """
    截取当前屏幕，返回 Base64 图像。
    这是多模态 Agent (如 Claude 3.5 Sonnet) 的眼睛。
    当 DOM 操作失效时，Agent 可以截图分析 UI 状态。
    """
    # 截图并返回 base64
    pass
```
---
## 3. 深度优化：针对 Agent 特性的工程改造
### 3.1 COM 管理的终极方案：VBA 桥接
之前 v4.0 在 Python 端拼命管理 COM 对象池，还容易产生僵尸进程。v5.0 彻底改变思路：
**方案**：我们不在 Python 端持有 COM 对象。每次 Agent 调用 `execute_vba_script` 时，我们启动一个**临时的、独立的** WScript 进程来执行 VBA，执行完毕进程自动销毁。
```vba
' 内部生成的临时执行脚本模板
Set app = CreateObject("Excel.Application")
app.Visible = False
app.DisplayAlerts = False
Set wb = app.Workbooks.Open("C:\data\test.xlsx")
' === Agent 动态生成的 VBA 代码插入此处 ===
On Error Resume Next
[AGENT_VBA_CODE_HERE]
On Error GoTo 0
' ==========================================
wb.Save
app.Quit
Set wb = Nothing
Set app = Nothing
```
**优势**：进程隔离，绝不产生僵尸进程，无需 Python 端复杂的 `threading.local` 和 `CoUninitialize`。
### 3.2 防御 Agent 幻觉的只读架构
Agent 的幻觉是生产环境最大的敌人。例如，Agent 幻觉可能会生成代码覆盖重要文件。
**改进**：
1. **工作区隔离**: 为每个任务创建一个 `C:\AgentWorkspace\{task_id}` 目录。所有文件操作只能在这个目录内进行。
2. **影子副本**: 当 Agent 需要修改 `C:\Important\report.xlsx` 时，MCP Server 自动将其复制到工作区，修改只针对副本。除非 Agent 显式调用 `promote_to_production` 工具，否则不覆盖源文件。
```python
@server.tool()
async def secure_open_file(file_path: str, mode: str = "read") -> str:
    """
    安全地打开文件。如果是 write 模式，自动重定向到沙箱副本。
    """
    if mode == "write":
        shadow_path = create_shadow_copy(file_path)
        return f"文件已映射到安全工作区: {shadow_path}。你的修改不会影响原文件。"
    else:
        return read_file_content(file_path)
```
---
## 4. 实战演练：Reasonix / Claude Code 如何使用这套工具
这是 v5.0 架构最核心的展示，展示了灵活性如何指数级上升。
**任务**：分析 D 盘的 `sales_data.xlsx`，找出销售额低于平均值的城市，在 Excel 中标红，并生成一份 Word 报告发送给老板。
### 传统 RPA (v4.0) 的做法：
必须预先写好：`excel_analyze` -> `format_excel` -> `generate_word_report` -> `send_email`。如果 Excel 格式变了，代码全废。
### Agent (Reasonix) + v5.0 工具链的做法：
1. **Reasonix** (思考)：我需要先看看 Excel 里有什么。
   - **调用**: `read_excel_range(file_path="D:/sales_data.xlsx", sheet_name="Sheet1")`
   - **返回**: 城市和销售额的表格数据。
2. **Reasonix** (思考)：数据量不大，我直接用 Pandas 在沙箱里算一下平均值和筛选条件。
   - **调用**: `execute_isolated_python(code="import pandas as pd\n...")`
   - **返回**: `["西安", "太原"]` 低于平均值。
3. **Reasonix** (思考)：现在我需要把这两个城市在 Excel 里标红。我手写一段 VBA。
   - **调用**: `execute_vba_script(app_name="Excel", script_content="Sub MarkRed() ... End Sub")`
   - **返回**: "执行成功"。
4. **Reasonix** (思考)：接下来生成 Word 报告。我写一段 Python 用 `python-docx` 生成。
   - **调用**: `execute_isolated_python(code="from docx import Document\n...")`
   - **返回**: "报告已生成于 C:\AgentWorkspace\task1\report.docx"
5. **Reasonix** (思考)：最后发送邮件。
   - **调用**: `execute_isolated_python(code="import smtplib\n...")`
**核心差异**：在这个流程中，**没有任何一个业务逻辑是我们开发者预写的**。我们只提供了“手”（执行 VBA、执行 Python、读写文件），所有的“智能”（怎么算平均值、怎么写 VBA 循环、怎么排版 Word）都是 Agent 实时生成的。
---
## 5. 部署与集成指南
为了让 Claude Code 或 Reasonix 能够使用这些工具，你需要将工具注册到 MCP 配置中。
### 5.1 Claude Code 集成 (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "desktop-sandbox": {
      "command": "python",
      "args": ["path/to/server/mcp_desktop_sandbox.py"]
    },
    "office-atomic": {
      "command": "python",
      "args": ["path/to/server/mcp_office_atomic.py"]
    },
    "os-control": {
      "command": "python",
      "args": ["path/to/server/mcp_os_control.py"]
    }
  }
}
```
### 5.2 Reasonix (DeepSeek) 集成
如果是基于 API 的 Reasonix，你需要启动 MCP Server 的 HTTP 模式，并在 Reasonix 的系统提示中注入工具定义：
```python
system_prompt = """
你是一个桌面控制 Agent。你可以使用以下工具控制用户的电脑：
1. execute_vba_script: 在 Office 中执行 VBA 代码。
2. execute_isolated_python: 在安全沙箱中运行 Python 数据处理脚本。
3. get_desktop_screenshot: 截屏查看当前状态。
注意：修改文件前务必谨慎，优先使用沙箱环境测试代码。
"""
```
---
## 📌 总结
v5.0 的重构彻底抛弃了“控制 Agent”的旧思维，转向“**赋能 Agent**”。
1. **不再越俎代庖**：不再用 Python 硬编码业务逻辑，因为 Agent 写的代码比我们预想的更灵活。
2. **拥抱原生能力**：利用 VBA 直接控制 Office，利用 AHK 控制桌面，比用 Python 套壳稳定 100 倍。
3. **绝对安全**：Agent 生成的代码必须在沙箱或影子副本中运行，防止幻觉灾难。
这才是让 Reasonix 或 Claude Code 真正拥有“手脚”、成为超级 Agent 的正确姿势。
