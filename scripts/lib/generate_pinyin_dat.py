"""
生成微软拼音输入法自学习词汇 .dat 文件（二进制格式）

格式参考开源项目 ms-user-dictcraft 的逆向工程结果：
  - 固定头部 64 字节（含魔数 "mschxudp"）
  - 偏移量表（每项 4 字节）
  - 条目数据块
"""
import os
import struct
import time

# ── 词库 ──
vocab = [
    # === 小金东个人信息 ===
    ("小金东", "xiao jin dong", 1),
    ("李金东", "li jin dong", 1),
    ("小金东的", "xiao jin dong de", 1),
    ("金东", "jin dong", 1),
    # === Reasonix 项目 ===
    ("Reasonix", "reasonix", 1),
    ("Reasonix桌面版", "reasonix zhuo mian ban", 1),
    ("截图监控", "jie tu jian kong", 1),
    ("截图监视器", "jie tu jian shi qi", 1),
    ("开机自启", "kai ji zi qi", 1),
    ("自学习", "zi xue xi", 1),
    ("自学习词汇", "zi xue xi ci hui", 1),
    ("用户定义短语", "yong hu ding yi duan yu", 1),
    ("输入准确率", "shu ru zhun que lv", 1),
    ("OpenCode", "opencode", 1),
    ("Web界面", "web jie mian", 1),
    ("Tailscale", "tailscale", 1),
    ("组网", "zu wang", 1),
    ("WSL", "wsl", 1),
    ("IDM", "idm", 1),
    ("静默下载", "jing mo xia zai", 1),
    # === AI 模型/平台 ===
    ("DeepSeek", "deepseek", 1),
    ("DeepSeek-Pro", "deepseek pro", 1),
    ("DeepSeek-Flash", "deepseek flash", 1),
    ("Qwen", "qwen", 1),
    ("通义千问", "tong yi qian wen", 1),
    ("千问", "qian wen", 1),
    ("百炼", "bai lian", 1),
    ("阿里云百炼", "a li yun bai lian", 1),
    ("DashScope", "dashscope", 1),
    ("ModelScope", "modelscope", 1),
    ("魔搭社区", "mo da she qu", 1),
    ("硅基流动", "gui ji liu dong", 1),
    ("SiliconFlow", "siliconflow", 1),
    ("PaddleOCR", "paddle ocr", 1),
    ("PaddleOCR-VL", "paddle ocr vl", 1),
    ("GPT-4o", "gpt 4 o", 1),
    ("GitHub Models", "github models", 1),
    ("竞速模式", "jing su mo shi", 1),
    ("兜底", "dou di", 1),
    ("级联竞速", "ji lian jing su", 1),
    ("多引擎", "duo yin qing", 1),
    # === TTS ===
    ("TTS", "tts", 1),
    ("语音合成", "yu yin he cheng", 1),
    ("EdgeTTS", "edge tts", 1),
    ("语音朗读", "yu yin lang du", 1),
    ("仿生机器人", "fang sheng ji qi ren", 1),
    ("语音播报", "yu yin bo bao", 1),
    # === OCR ===
    ("OCR", "ocr", 1),
    ("截图OCR", "jie tu ocr", 1),
    ("文字识别", "wen zi shi bie", 1),
    ("版面解析", "ban mian jie xi", 1),
    ("文字提取", "wen zi ti qu", 1),
    ("视觉模型", "shi jue mo xing", 1),
    ("多模态", "duo mo tai", 1),
    # === 编码技术 ===
    ("代码审查", "dai ma shen cha", 1),
    ("语法检查", "yu fa jian cha", 1),
    ("根因分析", "gen yin fen xi", 1),
    ("方案比选", "fang an bi xuan", 1),
    ("深度迭代", "shen du die dai", 1),
    ("纠偏", "jiu pian", 1),
    ("发版", "fa ban", 1),
    ("回滚", "hui gun", 1),
    ("归档", "gui dang", 1),
    ("微学习", "wei xue xi", 1),
    ("轮询", "lun xun", 1),
    ("校验", "xiao yan", 1),
    ("调试", "diao shi", 1),
    ("部署", "bu shu", 1),
    ("剪贴板", "jian tie ban", 1),
    ("快捷键", "kuai jie jian", 1),
    ("配置文件", "pei zhi wen jian", 1),
    ("环境变量", "huan jing bian liang", 1),
    ("异步", "yi bu", 1),
    ("并发", "bing fa", 1),
    ("线程池", "xian cheng chi", 1),
    ("端口", "duan kou", 1),
    ("锁文件", "suo wen jian", 1),
    # === 深度交流词汇 ===
    ("羁绊", "ji ban", 1),
    ("沉浸式", "chen jin shi", 1),
    ("第二大脑", "di er da nao", 1),
    ("思维融合", "si wei rong he", 1),
    ("智能体", "zhi neng ti", 1),
    ("进化", "jin hua", 1),
    ("自进化", "zi jin hua", 1),
    ("闭环", "bi huan", 1),
    ("持久化", "chi jiu hua", 1),
    ("Agent", "agent", 1),
    ("子代理", "zi dai li", 1),
    # === 常用术语 ===
    ("准确率", "zhun que lv", 1),
    ("键鼠模拟", "jian shu mo ni", 1),
    ("无弹窗", "wu tan chuang", 1),
    ("后台静默", "hou tai jing mo", 1),
    ("内存", "nei cun", 1),
    ("显卡", "xian ka", 1),
    ("笔记本", "bi ji ben", 1),
    ("台式机", "tai shi ji", 1),
    ("审计部", "shen ji bu", 1),
    ("中铁大桥局", "zhong tie da qiao ju", 1),
    ("西南科大", "xi nan ke da", 1),
    ("工程管理", "gong cheng guan li", 1),
    ("万州", "wan zhou", 1),
    ("重庆市", "chong qing shi", 1),
    ("素描", "su miao", 1),
    ("象棋", "xiang qi", 1),
    ("跑酷", "pao ku", 1),
]


def build_entry(pinyin: str, phrase: str, i_candidate: int = 1, sql_key: int = 0xBEEFCAFE) -> bytes:
    """构建单条自学习词汇条目"""
    pinyin_bytes = pinyin.encode("utf-16-le") + b"\x00\x00"
    phrase_bytes = phrase.encode("utf-16-le") + b"\x00\x00"

    # phrase_start = 16 (固定前缀) + len(pinyin_utf16le) + 2 (null)
    phrase_start = 16 + len(pinyin_bytes)

    entry = (
        b"\x10\x00\x10\x00"
        + struct.pack("<H", phrase_start)   # phrase 偏移
        + struct.pack("B", i_candidate)      # 候选位置 1-9
        + b"\x06"                            # 未知标志
        + b"\x00\x00\x00\x00"                # 保留
        + struct.pack("<I", sql_key)          # SQL key
        + pinyin_bytes
        + phrase_bytes
    )
    return entry


def generate_dat(output_path: str, items: list):
    """生成 .dat 二进制文件"""
    # 构建条目数据
    entries = [build_entry(p, w, c) for (w, p, c) in items]
    n = len(entries)

    # 计算偏移表和数据块大小
    items_start = 0x40 + 4 * n          # 头部(64) + 偏移表(n×4)
    data_length = items_start + sum(len(e) for e in entries)

    # ── 头部 64 字节 ──
    header = bytes([
        0x6D, 0x73, 0x63, 0x68,    # "msch"
        0x78, 0x75, 0x64, 0x70,    # "xudp"
        0x02, 0x00,                 # 版本
        0x60, 0x00,                 # ?
        0x01, 0x00, 0x00, 0x00,    # ?
        0x40, 0x00, 0x00, 0x00,    # 固定值
    ])
    header += struct.pack("<I", items_start)    # 条目起始偏移
    header += struct.pack("<I", data_length)    # 文件总长度
    header += struct.pack("<I", n)              # 条目数量
    header += struct.pack("<I", int(time.time()))  # UTC 时间戳
    header += b"\x00" * 28                      # 保留

    # ── 偏移量表 ──
    offsets = b""
    acc = 0
    for entry in entries:
        offsets += struct.pack("<I", acc)
        acc += len(entry)

    # ── 条目数据块 ──
    data_block = b"".join(entries)

    # 写入文件
    with open(output_path, "wb") as f:
        f.write(header)
        f.write(offsets)
        f.write(data_block)

    file_size = os.path.getsize(output_path)
    print(f"✅ 已生成: {output_path}")
    print(f"   大小: {file_size:,} 字节")
    print(f"   词条: {n}")
    print(f"   文件头校验: {header[:20].hex()}")
    print(f"   数据偏移: {items_start}")
    print(f"   文件长度: {data_length}")

    # 验证：重新读取并解析
    verify_dat(output_path)


def verify_dat(file_path: str):
    """验证生成的 .dat 文件格式是否正确"""
    with open(file_path, "rb") as f:
        data = f.read()

    # 检查魔数
    magic = data[:8]
    assert magic == b"mschxudp", f"魔数错误: {magic}"

    # 解析头部
    items_start = struct.unpack("<I", data[20:24])[0]
    data_length = struct.unpack("<I", data[24:28])[0]
    n = struct.unpack("<I", data[28:32])[0]
    timestamp = struct.unpack("<I", data[32:36])[0]

    assert items_start == 0x40 + 4 * n, f"偏移量错误: {items_start} != {0x40 + 4 * n}"
    assert data_length == len(data), f"长度错误: {data_length} != {len(data)}"
    assert data[36:64] == b"\x00" * 28, "保留字段非零"

    # 校验前 20 字节固定签名
    expected_fixed = bytes([
        0x6D, 0x73, 0x63, 0x68,
        0x78, 0x75, 0x64, 0x70,
        0x02, 0x00, 0x60, 0x00,
        0x01, 0x00, 0x00, 0x00,
        0x40, 0x00, 0x00, 0x00,
    ])
    assert data[:20] == expected_fixed, f"固定头错误"

    print(f"✅ 校验通过: {n} 条词条, 时间戳 {timestamp}")


if __name__ == "__main__":
    output = r"D:\Reasonix\自学习词汇.dat"
    generate_dat(output, vocab)
