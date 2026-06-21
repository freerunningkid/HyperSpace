"""
聊天记录归档工具
从 ~/.claude/projects/ 读取 JSONL 会话文件，提取有效对话内容，
生成结构化的 Markdown 文件到 03-历史聊天/ 目录。

用法：
  python scripts/tools/chat_archive.py                                    # 处理所有 JSONL
  python scripts/tools/chat_archive.py --incremental                       # 只处理新增/更新的文件
  python scripts/tools/chat_archive.py --extract                           # 提取知识到记忆/知识库
  python scripts/tools/chat_archive.py --archive-and-extract               # 归档 + 提取
  python scripts/tools/chat_archive.py --incremental --quiet               # 静默模式
  python scripts/tools/chat_archive.py --dry-run                           # 预览模式
  python scripts/tools/chat_archive.py --file <uuid>                       # 只处理指定 UUID
  python scripts/tools/chat_archive.py --since 2026-05-28                  # 只处理某天之后的
"""

import json
import os
import re
import sys
import glob
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ====== 配置 ======
PROJECT_DIR = os.path.expanduser(r"~/.claude/projects/D--Reasonix")
OUTPUT_DIR = r"D:\Reasonix\reference-参考\chat-archives"
MEMORY_DIR = r"D:\Reasonix\memory"
SHARED_MEMORY_DIR = r"D:\Reasonix\bridge"
KNOWLEDGE_BASE = r"D:\Reasonix\knowledge-知识库\问题解决记录.md"
CST = timezone(timedelta(hours=8))  # 中国时区

# 不提取的附件类型
SKIP_ATTACHMENT_TYPES = {'skill_listing', 'todo_reminder', 'context_reminder'}
# 提取的最大文件大小（超过此大小的将分段归档）
MAX_SINGLE_FILE_SIZE = 500 * 1024  # 500KB

# ====== 辅助函数 ======

def parse_timestamp(ts_str):
    """解析 ISO 时间戳为 datetime"""
    if not ts_str:
        return None
    try:
        ts = ts_str
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        return datetime.fromisoformat(ts)
    except:
        return None

def extract_text(content):
    """从 message.content 提取纯文本"""
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'text':
                texts.append(block.get('text', ''))
        return '\n'.join(texts)
    return str(content)

def is_noise_line(text):
    """判断是否为噪音行（空行、纯标点、极短行）"""
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) < 3:
        return True
    # 纯标点/符号
    if re.match(r'^[\s\.,!?;:，。！？；：、…—\-_#*~`@\[\]\(\){}<>/\\\|""''""'']+$', stripped):
        return True
    return False

def generate_summary(text, max_len=50):
    """从对话文本生成摘要标题"""
    # 取第一段有意义的文本
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not is_noise_line(line) and len(line) >= 4:
            # 截取有意义的片段
            clean = re.sub(r'[^一-鿿\w\s]', '', line)
            clean = clean.strip()
            if len(clean) > max_len:
                clean = clean[:max_len]
            if clean:
                return clean
    return "未命名对话"


def parse_jsonl(filepath):
    """解析单个 JSONL 文件，返回结构化的对话数据"""
    messages = []
    session_start = None
    session_end = None
    title_candidates = []

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = parse_timestamp(entry.get('timestamp'))
            if not ts:
                continue

            if session_start is None or ts < session_start:
                session_start = ts
            if session_end is None or ts > session_end:
                session_end = ts

            entry_type = entry.get('type', '')

            # 收集 AI 生成的标题
            if entry_type == 'ai-title':
                title_text = entry.get('title', '')
                if title_text:
                    title_candidates.append(title_text)
                continue

            # 跳过系统噪音
            if entry_type in ('queue-operation', 'file-history-snapshot', 'last-prompt', 'permission-mode'):
                continue

            # 附件（技能列表等）
            if entry_type == 'attachment':
                att_type = entry.get('attachment', {}).get('type', '')
                if att_type not in SKIP_ATTACHMENT_TYPES:
                    att_content = entry.get('attachment', {}).get('content', '')
                    if isinstance(att_content, str) and att_content.strip():
                        messages.append({
                            'role': 'system',
                            'content': att_content,
                            'timestamp': ts
                        })
                continue

            # 用户消息
            if entry_type == 'user':
                msg = entry.get('message', {})
                content = extract_text(msg.get('content', ''))
                if content.strip():
                    messages.append({
                        'role': 'user',
                        'content': content.strip(),
                        'timestamp': ts
                    })
                continue

            # 助手回复
            if entry_type == 'assistant':
                msg = entry.get('message', {})
                content = extract_text(msg.get('content', ''))
                if content.strip():
                    messages.append({
                        'role': 'assistant',
                        'content': content.strip(),
                        'timestamp': ts
                    })
                continue

    return {
        'messages': messages,
        'start_time': session_start,
        'end_time': session_end,
        'title_candidates': title_candidates,
        'filepath': filepath,
    }


def format_duration(start, end):
    """格式化会话时长"""
    if not start or not end:
        return "未知"
    delta = end - start
    total_minutes = int(delta.total_seconds() / 60)
    if total_minutes < 1:
        return "1 分钟内"
    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours > 0:
        return f"{hours} 小时 {mins} 分钟"
    return f"{mins} 分钟"


def classify_conversation(messages):
    """根据消息内容推断对话类型和话题标签"""
    all_text = ' '.join(m.get('content', '') for m in messages if m.get('role') == 'user')

    topics = []

    # 话题关键词匹配
    topic_keywords = {
        '编程/开发': ['代码', '实现', 'bug', 'error', '报错', '调试', '部署', '重构', '优化', '修复', '函数', '类', '接口', 'API'],
        '系统配置': ['安装', '配置', '环境', '路径', '变量', '注册表', '服务', '启动', '设置'],
        '知识管理': ['记忆', '知识库', '笔记', '归档', '规则', 'CLAUDE.md', 'rules', 'hooks'],
        '工具/软件': ['GitHub', 'git', '同步', 'sync', 'push', 'pull', '脚本', '工具'],
        '文件操作': ['文件', '目录', '文件夹', '删除', '移动', '重命名', '备份', '整理'],
        'AI/模型': ['模型', 'token', '上下文', '提示词', 'prompt', 'Claude', 'DeepSeek', 'API'],
        '网络/通信': ['Tailscale', '网络', 'SSH', 'RDP', '远程', '手机'],
        '硬件/设备': ['内存', '磁盘', '硬盘', 'CPU', '显卡', '驱动', '显示器', '屏幕'],
        '生活/个人': ['骑行', '摩托', '体检', '健康', '生日', '生日'],
        '工作/审计': ['审计', '财务', '账面', '报表', '凭证', '入账'],
    }

    for topic, keywords in topic_keywords.items():
        for kw in keywords:
            if kw in all_text:
                topics.append(topic)
                break

    if not topics:
        topics = ['其他']

    return topics


def clean_message_content(content, max_length=2000):
    """清理消息内容：去噪音、截断"""
    lines = content.split('\n')
    cleaned = []
    for line in lines:
        if not is_noise_line(line):
            cleaned.append(line)

    result = '\n'.join(cleaned)
    if len(result) > max_length * 3:  # 对超长内容仅保留关键部分
        # 保留开头和结尾
        result = result[:max_length] + '\n\n...(中间内容省略)...\n\n' + result[-max_length//2:]
    return result


def write_md_file(session, output_dir):
    """将解析结果写入结构化的 MD 文件"""
    messages = session['messages']
    if not messages:
        return None

    # 确定标题
    title = ""
    if session['title_candidates']:
        title = session['title_candidates'][-1]  # 取最后一个 AI 生成的标题
    else:
        # 从第一条用户消息提取
        for m in messages:
            if m['role'] == 'user':
                title = generate_summary(m['content'])
                break

    if not title:
        title = "未命名对话"

    # 清理标题中的非法文件名字符
    safe_title = re.sub(r'[\\/:*?"<>|]', '·', title)
    safe_title = safe_title.strip()
    if len(safe_title) > 60:
        safe_title = safe_title[:60]

    # 时间戳
    start_time = session['start_time']
    ts_str = start_time.strftime('%Y%m%d_%H%M%S') if start_time else 'unknown'
    date_str = start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else '未知'
    end_str = session['end_time'].strftime('%Y-%m-%d %H:%M:%S') if session['end_time'] else '未知'
    duration = format_duration(session['start_time'], session['end_time'])

    # 话题分类
    topics = classify_conversation(messages)

    # 文件名
    filename = f"对话-{safe_title}-{ts_str}.md"
    filepath = os.path.join(output_dir, filename)

    # 统计信息
    user_msg_count = sum(1 for m in messages if m['role'] == 'user')
    asst_msg_count = sum(1 for m in messages if m['role'] == 'assistant')

    # --- 写入文件 ---
    with open(filepath, 'w', encoding='utf-8') as f:
        # 标题
        f.write(f"# {title}\n\n")

        # 元信息区
        f.write("---\n\n")
        f.write(f"**日期**：{date_str}\n\n")
        f.write(f"**结束**：{end_str}\n\n")
        f.write(f"**时长**：{duration}\n\n")
        f.write(f"**消息数**：用户 {user_msg_count} 条 · 助手 {asst_msg_count} 条\n\n")
        f.write(f"**话题标签**：{'、'.join(topics)}\n\n")
        f.write(f"**源文件**：`{os.path.basename(session['filepath'])}`\n\n")
        f.write("---\n\n")

        # 对话正文
        f.write("## 对话内容\n\n")

        for i, msg in enumerate(messages):
            role_display = "👤 **小金东**" if msg['role'] == 'user' else "🌸 **2B**"
            ts = msg['timestamp'].strftime('%H:%M') if msg['timestamp'] else ''

            content = msg['content']
            # 对代码块做缩进处理
            content = clean_message_content(content)

            f.write(f"### {role_display} ({ts})\n\n")
            f.write(content + "\n\n")

            # 消息之间加分隔线
            if i < len(messages) - 1:
                f.write("---\n\n")

        # 结束标记
        f.write(f"\n> 归档时间：{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}\n")

    return filepath


def needs_update(jsonl_path, output_dir):
    """检查 JSONL 是否需要重新归档（无 MD 输出或 JSONL 比 MD 新）"""
    # 从 JSONL 文件名推断可能的 MD 文件名？没法直接推，只能先处理再对比。
    # 更简单的策略：检查 JSONL 的 mtime 与 output_dir 中最近 MD 文件的 mtime
    # 实际上最好记录已处理的 JSONL 列表。但为了简单，我们用 mtime 对比。
    # 如果 output_dir 中不存在任何比该 JSONL 更新的 MD 文件，则需要处理。
    jsonl_mtime = os.path.getmtime(jsonl_path)

    # 检查输出目录中是否有文件比这个 JSONL 更新
    if not os.path.isdir(output_dir):
        return True

    # 快速检查：获取输出目录中最新的 MD 文件的 mtime
    try:
        md_files = glob.glob(os.path.join(output_dir, "*.md"))
        if not md_files:
            return True
        latest_md = max(os.path.getmtime(f) for f in md_files)
        # 如果最新 MD 比 JSONL 还旧，说明有新 JSONL 没处理
        return jsonl_mtime > latest_md + 60  # 60秒缓冲
    except:
        return True


# ====== 知识提取引擎 ======

# 判定为"有价值"的关键词（问题→解决方案模式）
VALUE_KEYWORDS = {
    'problem_solution': [
        '问题', '错误', '报错', '修复', '解决', '排查',
        '根因', '原因', '导致', '方案', '步骤', '方法',
        '注意', '经验', '教训', '总结',
    ],
    'configuration': [
        '安装', '配置', '部署', '设置', '注册',
        '路径', '端口', '命令', '参数', '选项',
    ],
    'reference': [
        '是什么', '什么是', '怎么用', '如何使用',
        '推荐', '对比', '比较', '哪个好', '的区别',
    ],
    'preference': [
        '我喜欢', '我不喜欢', '帮我记住',
        '以后不要', '以后要', '我觉得', '我认为',
    ],
}

# 跳过关键词（纯测试/问候/日常操作，无价值）
SKIP_KEYWORDS = [
    'say hello', 'echo hi', 'say hi', 'ping', 'pong',
    '你好', '在吗', '你是谁',
]

# 噪音话题——即使匹配了关键词也跳过
NOISE_TOPICS = [
    '拉一下github', '推github', '同步一下github', '拉一下guthub',
    '明天天气', '今天天气', '天气如何',
    '帮我找下', '帮我查下', '帮我搜',
]

# 高质量提取的最低关键词命中数（同类型内）
MIN_KEYWORD_MATCHES = {
    'problem_solution': 2,    # 问题和方案关键词都要出现
    'configuration': 2,
    'reference': 1,
    'preference': 1,
}


def compute_content_hash(text):
    """计算内容哈希，用于去重"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]


def get_existing_hashes():
    """读取已提取知识的哈希集合，避免重复"""
    hashes = set()
    hash_file = os.path.join(OUTPUT_DIR, '.extracted_hashes.txt')
    if os.path.exists(hash_file):
        with open(hash_file, 'r') as f:
            for line in f:
                h = line.strip()
                if h:
                    hashes.add(h)
    return hashes, hash_file


def save_extracted_hash(content_hash, hash_file):
    """记录已提取的哈希"""
    with open(hash_file, 'a') as f:
        f.write(content_hash + '\n')


def infer_types(text):
    """从文本中推断知识类型（仅用于分类标签）"""
    types = set()
    if any(kw in text for kw in ['问题', '错误', '报错', '修复', '解决', '排查', '根因']):
        types.add('problem_solution')
    if any(kw in text for kw in ['安装', '配置', '部署', '设置', '注册', '路径', '端口']):
        types.add('configuration')
    if any(kw in text for kw in ['推荐', '对比', '比较', '怎么用', '如何使用']):
        types.add('reference')
    if any(kw in text for kw in ['我喜欢', '我不喜欢', '帮我记住', '以后不要']):
        types.add('preference')
    return types if types else {'reference'}


def is_valuable_conversation(messages):
    """判断对话是否值得提取知识（严格模式）

    必须同时满足：
    1. >= 8 条用户消息
    2. 助手回复含代码块
    3. 用户同时提到问题和解决相关词
    4. 不是 git 操作/简单查询
    """
    user_msgs = [m for m in messages if m['role'] == 'user']
    asst_msgs = [m for m in messages if m['role'] == 'assistant']

    if len(user_msgs) < 8:
        return False, set(), 0

    user_text = '\n'.join(m['content'] for m in user_msgs)
    asst_text = '\n'.join(m['content'] for m in asst_msgs)
    low_user = user_text.lower()

    # 必须：助手回复含代码块
    if '```' not in asst_text:
        return False, set(), 0

    # 必须：用户提到问题和解决
    has_problem = any(kw in user_text for kw in ['问题', '错误', '报错', 'bug', 'error', '异常', '失败'])
    has_fix = any(kw in user_text for kw in ['修复', '解决', '方案', '配置', '设置', '怎么', '如何'])
    if not (has_problem and has_fix):
        return False, set(), 0

    # 排除：git 操作
    for noise in NOISE_TOPICS:
        if noise in user_text:
            return False, set(), 0

    return True, infer_types(user_text + '\n' + asst_text), 0


def extract_knowledge_from_session(session, archived_file):
    """从已归档的对话中提取结构化知识"""
    messages = session['messages']
    is_valuable, _, score = is_valuable_conversation(messages)
    if not is_valuable:
        return None

    # 推断价值类型（辅助分类，不影响提取判断）
    all_text = '\n'.join(m['content'] for m in messages)
    value_types = infer_types(all_text)

    # 提取关键信息
    title = ""
    if session['title_candidates']:
        title = session['title_candidates'][-1]
    else:
        for m in messages:
            if m['role'] == 'user':
                title = generate_summary(m['content'])
                break

    if not title:
        title = "未命名对话"

    # 提取问题描述（第一条有意义的用户消息）
    problem = ""
    for m in messages:
        if m['role'] == 'user':
            c = m['content'].strip()
            if len(c) > 10:
                problem = c[:300]
                break

    # 提取解决方案（最后几条助手回复）
    solutions = []
    for m in reversed(messages):
        if m['role'] == 'assistant' and len(m['content'].strip()) > 50:
            solutions.append(m['content'].strip()[:500])
            if len(solutions) >= 2:
                break

    # 时间信息
    start_ts = session['start_time']
    date_str = start_ts.strftime('%Y-%m-%d') if start_ts else '未知'

    return {
        'title': title,
        'date': date_str,
        'value_types': value_types,
        'problem': problem,
        'solutions': solutions,
        'source': os.path.basename(archived_file),
        'messages': messages,
    }


def format_as_memory_entry(knowledge):
    """将提取的知识格式化为记忆条目文本"""
    lines = []
    lines.append(f"# {knowledge['title']}\n")
    lines.append(f"\n> 自动提取自 {knowledge['date']} 的对话 | 类型: {', '.join(knowledge['value_types'])}\n")
    lines.append(f"\n## 问题\n\n{knowledge['problem']}\n")

    if knowledge['solutions']:
        lines.append(f"\n## 方案\n")
        for i, sol in enumerate(knowledge['solutions'], 1):
            lines.append(f"\n{i}. {sol}\n")

    lines.append(f"\n## 来源\n\n`{knowledge['source']}`\n")
    lines.append(f"\n---\n*归档时间：{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}*\n")
    return ''.join(lines)


def write_to_knowledge_base(knowledge):
    """将问题→解决方案追加到问题解决记录.md"""
    # 读取现有内容
    kb_path = KNOWLEDGE_BASE
    existing = ""
    if os.path.exists(kb_path):
        with open(kb_path, 'r', encoding='utf-8') as f:
            existing = f.read()

    # 构建新条目
    title = knowledge['title']
    # 清理标题中的非法文件名字符（只用于显示）
    clean_title = re.sub(r'[\\/:*?"<>|]', '·', title)
    date = knowledge['date']
    problem = knowledge['problem']
    solutions = knowledge['solutions']
    source = knowledge['source']

    entry = f"\n## {date}：{clean_title}\n\n"
    entry += f"- **问题**: {problem}\n"

    if solutions:
        entry += f"- **方案**:\n"
        for sol in solutions:
            entry += f"  1. {sol}\n"

    entry += f"- **来源**: `{source}`\n"
    entry += f"- **提取时间**: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}\n"

    # 追加到文件（时间倒序，插在第一个条目之前）
    # 找到第一个 "## " 的位置，在其后插入
    first_entry = existing.find('\n## ')
    if first_entry > 0:
        # 在第一个条目前插入
        new_content = existing[:first_entry] + entry + existing[first_entry:]
    else:
        new_content = existing + entry

    # 写回
    os.makedirs(os.path.dirname(kb_path), exist_ok=True)
    with open(kb_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return entry


def write_to_memory(knowledge):
    """将知识写入 memory/*.md 文件并更新 MEMORY.md"""
    # 确定记忆类型
    vtypes = knowledge['value_types']
    if 'preference' in vtypes:
        mem_type = 'feedback' if '以后' in knowledge['problem'] or '我' in knowledge['problem'] else 'user'
    elif 'configuration' in vtypes or 'reference' in vtypes:
        mem_type = 'reference'
    else:
        mem_type = 'reference'

    # 生成安全的文件名
    safe_title = re.sub(r'[\\/:*?"<>|]', '·', knowledge['title'])
    safe_title = safe_title.strip()[:50]
    ts = datetime.now(CST).strftime('%Y%m%d_%H%M%S')
    filename = f"extracted_{safe_title}_{ts}.md"
    filepath = os.path.join(MEMORY_DIR, filename)

    # 格式化内容
    content = f"""---
name: extracted-{safe_title[:30]}
description: {knowledge['problem'][:80]}
metadata:
  type: {mem_type}
  source: auto-extract
---

# {knowledge['title']}

**提取日期**：{knowledge['date']}

## 概述

{knowledge['problem']}

## 详细内容

"""
    if knowledge['solutions']:
        content += "### 方案\n\n"
        for i, sol in enumerate(knowledge['solutions'], 1):
            content += f"{i}. {sol}\n\n"

    content += f"\n---\n*自动提取自 `{knowledge['source']}`*\n"

    # 写入文件
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    # 同步到 shared_memory
    shared_path = os.path.join(SHARED_MEMORY_DIR, filename)
    os.makedirs(SHARED_MEMORY_DIR, exist_ok=True)
    with open(shared_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 更新 MEMORY.md
    mem_index = os.path.join(MEMORY_DIR, 'MEMORY.md')
    shared_index = os.path.join(SHARED_MEMORY_DIR, 'MEMORY.md')
    hook = f"- [{knowledge['title'][:50]}]({filename}) — {knowledge['problem'][:80]}"

    for idx_path in [mem_index, shared_index]:
        if os.path.exists(idx_path):
            with open(idx_path, 'r', encoding='utf-8') as f:
                idx_content = f.read()
        else:
            idx_content = ""
        # 追加到末尾
        with open(idx_path, 'a', encoding='utf-8') as f:
            f.write(hook + '\n')

    return filepath


def extract_from_archived(filepath, quiet=False):
    """从单个已归档的 MD 文件中提取知识"""
    # 读取 MD 文件
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 用哈希去重
    content_hash = compute_content_hash(content)
    existing_hashes, hash_file = get_existing_hashes()
    if content_hash in existing_hashes:
        if not quiet:
            print(f"  [提取] {os.path.basename(filepath)} → 已提取过，跳过")
        return None

    # 从 MD 文件反解出 session 结构
    # 提取标题
    title_match = re.search(r'^# (.+)', content)
    title = title_match.group(1) if title_match else "未命名"

    # 提取日期
    date_match = re.search(r'\*\*日期\*\*：(.+)', content)
    date_str = date_match.group(1).strip() if date_match else "未知"

    # 提取标签
    tags_match = re.search(r'\*\*话题标签\*\*：(.+)', content)
    tags = tags_match.group(1).strip() if tags_match else ""

    # 提取消息
    messages = []
    # 查找所有 ### 开头的对话角色行
    parts = re.split(r'### (.+?) \((\d+:\d+)\)\n\n', content)
    # parts 结构: [前文, role1, ts1, content1, role2, ts2, content2, ...]
    i = 1
    while i + 2 < len(parts):
        role_line = parts[i].strip()
        ts = parts[i+1].strip()
        msg_content = parts[i+2].strip()
        # 确定角色
        if '小金东' in role_line:
            role = 'user'
        elif '2B' in role_line:
            role = 'assistant'
        else:
            role = 'system'
        messages.append({'role': role, 'content': msg_content, 'timestamp': ts})
        i += 3

    # 构建 session 对象
    session = {
        'messages': messages,
        'title_candidates': [title] if title != "未命名" else [],
        'start_time': parse_timestamp(date_str) if date_str != "未知" else None,
        'end_time': None,
        'filepath': filepath,
    }

    # 提取知识
    knowledge = extract_knowledge_from_session(session, filepath)
    if not knowledge:
        # 记录哈希避免下次再检查
        save_extracted_hash(content_hash, hash_file)
        return None

    # 写入记忆
    result = {'knowledge': knowledge}

    # 写入问题解决记录
    if 'problem_solution' in knowledge['value_types']:
        try:
            entry = write_to_knowledge_base(knowledge)
            result['kb_entry'] = entry
        except Exception as e:
            if not quiet:
                print(f"  [提取] 写入知识库失败: {e}")

    # 写入 memory 文件
    try:
        mem_path = write_to_memory(knowledge)
        result['mem_path'] = mem_path
    except Exception as e:
        if not quiet:
            print(f"  [提取] 写入记忆失败: {e}")

    # 记录已提取哈希
    save_extracted_hash(content_hash, hash_file)

    return result


def run_extraction(archived_files, quiet=False):
    """批量提取知识"""
    if not archived_files:
        if not quiet:
            print("没有找到可提取的归档文件")
        return

    stats = {'extracted': 0, 'skipped': 0, 'errors': 0}

    for filepath in sorted(archived_files):
        filename = os.path.basename(filepath)
        # 跳过月份目录本身
        if not filename.endswith('.md'):
            continue

        if not quiet:
            print(f"  [分析] {filename}...", end=' ', flush=True)

        try:
            result = extract_from_archived(filepath, quiet=quiet)
            if result:
                stats['extracted'] += 1
                kb_info = " [KB]" if result.get('kb_entry') else ""
                mem_info = " [MEM]" if result.get('mem_path') else ""
                if not quiet:
                    print(f"[OK]  已提取 {kb_info}{mem_info}")
            else:
                stats['skipped'] += 1
                if not quiet:
                    print()  # extract_from_archived already printed the reason
        except Exception as e:
            stats['errors'] += 1
            if not quiet:
                print(f"[ERR]  错误: {e}")

    if not quiet:
        print(f"\n  ✨ 提取完成：成功 {stats['extracted']}，跳过 {stats['skipped']}，错误 {stats['errors']}")


def find_newly_archived_files(since_time=None):
    """查找新归档的 MD 文件"""
    md_files = []
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for f in files:
            if f.endswith('.md'):
                path = os.path.join(root, f)
                if since_time is None or os.path.getmtime(path) >= since_time:
                    md_files.append(path)
    return md_files


def main():
    # 参数解析
    dry_run = '--dry-run' in sys.argv
    incremental = '--incremental' in sys.argv
    quiet = '--quiet' in sys.argv
    extract = '--extract' in sys.argv
    archive_and_extract = '--archive-and-extract' in sys.argv
    only_file = None
    since_date = None

    for arg in sys.argv[1:]:
        if arg.startswith('--since='):
            since_date = arg.split('=', 1)[1]
        elif arg.startswith('--file='):
            only_file = arg.split('=', 1)[1]
        elif arg == '--dry-run':
            pass
        elif arg == '--incremental':
            pass
        elif arg == '--quiet':
            pass
        elif arg == '--extract':
            pass
        elif arg == '--archive-and-extract':
            pass
        elif arg.startswith('--'):
            print(f"未知参数: {arg}")
            print("用法: python chat_archive.py [--dry-run] [--incremental] [--extract] [--file=<uuid>] [--since=YYYY-MM-DD]")
            return

    # 纯提取模式：跳过归档，直接提取
    if extract and not archive_and_extract:
        if not quiet:
            print(f"纯提取模式：从已归档文件中提取知识...")
        all_md = find_newly_archived_files()
        run_extraction(all_md, quiet=quiet)
        return

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 获取所有 JSONL 文件
    pattern = os.path.join(PROJECT_DIR, "*.jsonl")
    files = sorted(glob.glob(pattern), key=lambda p: os.path.getmtime(p))

    if only_file:
        files = [f for f in files if only_file in f]

    if since_date:
        threshold = datetime.strptime(since_date, '%Y-%m-%d').replace(tzinfo=CST)
        files = [f for f in files if datetime.fromtimestamp(os.path.getmtime(f), tz=CST) >= threshold]

    if not files:
        if not quiet:
            print("没有找到匹配的聊天记录文件")
        return

    if not quiet:
        print(f"找到 {len(files)} 个聊天记录文件")

    stats = {'processed': 0, 'skipped': 0, 'errors': 0, 'empty': 0}

    for filepath in files:
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)

        # 跳过极小的文件（可能只是测试/空会话）
        if file_size < 1000:
            if dry_run or (incremental and not quiet):
                print(f"  [跳过] {filename} (过小: {file_size} bytes)")
            stats['skipped'] += 1
            continue

        # 增量模式：跳过已归档且无更新的文件
        if incremental and not needs_update(filepath, OUTPUT_DIR):
            if not quiet:
                print(f"  [最新] {filename} (已归档)")
            stats['skipped'] += 1
            continue

        if dry_run:
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%m-%d %H:%M')
            print(f"  [FILE] {filename} ({file_size//1024}KB, {mtime})")
            continue

        if not quiet:
            print(f"  [处理] {filename} ({file_size//1024}KB)...", end=' ', flush=True)

        try:
            session = parse_jsonl(filepath)

            # 检查是否有有效消息
            if not session['messages']:
                print("跳过（无有效消息）")
                stats['empty'] += 1
                continue

            # 写入 MD
            result = write_md_file(session, OUTPUT_DIR)

            if result:
                if not quiet:
                    print(f"[OK] -> {os.path.basename(result)}")
                stats['processed'] += 1
            else:
                if not quiet:
                    print("跳过（生成失败）")
                stats['empty'] += 1

        except Exception as e:
            if not quiet:
                print(f"[ERR] 错误: {e}")
            stats['errors'] += 1

    if not dry_run:
        if not quiet:
            print(f"\n{'='*50}")
            print(f"处理完成！")
            print(f"  成功归档：{stats['processed']} 个文件")
            print(f"  跳过（过小）：{stats['skipped']} 个")
            print(f"  跳过（无内容）：{stats['empty']} 个")
            print(f"  错误：{stats['errors']} 个")
            print(f"  输出目录：{OUTPUT_DIR}")

        # 提取知识（如果指定了 --extract 或 --archive-and-extract）
        if extract or archive_and_extract:
            if not quiet:
                print(f"\n{'='*50}")
                print(f"[提取] 开始提取知识到记忆/知识库...")
                print(f"  （已提取过的会话会自动跳过）\n")
            new_files = find_newly_archived_files()
            run_extraction(new_files, quiet=quiet)

    else:
        print(f"\n预览模式：共 {len(files)} 个文件，跳过 {stats['skipped']} 个过小文件")


if __name__ == '__main__':
    main()
