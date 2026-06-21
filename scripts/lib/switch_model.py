#!/usr/bin/env python3
"""Claude Code 模型切换工具 — DeepSeek / Agnes / GLM 一键切换

API Key 从环境变量读取，不在代码中硬编码。

用法:
  python scripts/lib/switch_model.py              # 查看当前模型
  python scripts/lib/switch_model.py deepseek      # 切到 DeepSeek
  python scripts/lib/switch_model.py agnes         # 切到 Agnes
  python scripts/lib/switch_model.py glm           # 切到 GLM (智谱AI)
  python scripts/lib/switch_model.py --list        # 列出可用配置

环境变量:
  DEEPSEEK_API_KEY     DeepSeek API Key
  AGNES_API_KEY        Agnes API Key
"""

import json
import sys
import os
import subprocess

SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXY_SCRIPT = os.path.join(SCRIPT_DIR, "model_proxy.py")


def _get_api_key(env_var, fallback_token="proxy-key"):
    """从环境变量获取 API Key，找不到则返回 fallback（用于代理模式）"""
    return os.environ.get(env_var, fallback_token)


PROFILES = {
    "deepseek": {
        "name": "DeepSeek V4 Flash",
        "description": "直连 DeepSeek 官方 API，缓存命中 98% off",
        "type": "direct",
        "api_key_env": "DEEPSEEK_API_KEY",
        "env": {
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "deepseek-v4-flash",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro[1M]",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "deepseek-v4-pro",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-flash[1M]",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "deepseek-v4-flash",
            "ANTHROPIC_MODEL": "deepseek-v4-flash",
            "ANTHROPIC_REASONING_MODEL": "deepseek-ai/DeepSeek-V4-Flash",
        }
    },
    "agnes": {
        "name": "Agnes 2.0 Flash",
        "description": "直连 Agnes AI API，1M 上下文，vLLM 推理",
        "type": "direct",
        "api_key_env": "AGNES_API_KEY",
        "env": {
            "ANTHROPIC_BASE_URL": "https://apihub.agnes-ai.com/v1",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "agnes-2.0-flash",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "agnes-2.0-flash",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "agnes-2.0-flash",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "agnes-2.0-flash",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "agnes-2.0-flash",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "agnes-2.0-flash",
            "ANTHROPIC_MODEL": "agnes-2.0-flash",
            "ANTHROPIC_REASONING_MODEL": "agnes-2.0-flash",
        }
    },
    "glm": {
        "name": "GLM-4.7-Flash (智谱AI)",
        "description": "通过本地翻译代理访问，需启动 model_proxy.py",
        "type": "proxy",
        "api_key_env": "ZHIPU_API_KEY",
        "env": {
            "ANTHROPIC_AUTH_TOKEN": "proxy-key",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7-flash",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "glm-4.7-flash",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-4.7-flash",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "glm-4.7-flash",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-4.7-flash",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "glm-4.7-flash",
            "ANTHROPIC_MODEL": "glm-4.7-flash",
            "ANTHROPIC_REASONING_MODEL": "glm-4.7-flash",
        }
    },
    "siliconflow": {
        "name": "Qwen2.5-32B (硅基流动)",
        "description": "通过本地翻译代理访问",
        "type": "proxy",
        "api_key_env": "SILICONFLOW_API_KEY",
        "env": {
            "ANTHROPIC_AUTH_TOKEN": "proxy-key",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "siliconflow-qwen-32b",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "siliconflow-qwen-32b",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "siliconflow-qwen-32b",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "siliconflow-qwen-32b",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "siliconflow-qwen-32b",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "siliconflow-qwen-32b",
            "ANTHROPIC_MODEL": "siliconflow-qwen-32b",
            "ANTHROPIC_REASONING_MODEL": "siliconflow-qwen-32b",
        }
    },
    "groq": {
        "name": "Llama 4 Fast (Groq)",
        "description": "通过本地翻译代理访问",
        "type": "proxy",
        "api_key_env": "GROQ_API_KEY",
        "env": {
            "ANTHROPIC_AUTH_TOKEN": "proxy-key",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "groq-llama-4-fast",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "groq-llama-4-fast",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "groq-llama-4-fast",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "groq-llama-4-fast",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "groq-llama-4-fast",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "groq-llama-4-fast",
            "ANTHROPIC_MODEL": "groq-llama-4-fast",
            "ANTHROPIC_REASONING_MODEL": "groq-llama-4-fast",
        }
    },
    "dashscope": {
        "name": "Qwen-Plus (DashScope)",
        "description": "通过本地翻译代理访问",
        "type": "proxy",
        "api_key_env": "DASHSCOPE_API_KEY",
        "env": {
            "ANTHROPIC_AUTH_TOKEN": "proxy-key",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "dashscope-qwen-plus",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "dashscope-qwen-plus",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "dashscope-qwen-plus",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "dashscope-qwen-plus",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "dashscope-qwen-plus",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "dashscope-qwen-plus",
            "ANTHROPIC_MODEL": "dashscope-qwen-plus",
            "ANTHROPIC_REASONING_MODEL": "dashscope-qwen-plus",
        }
    },
    "proxy": {
        "name": "本地翻译代理 (统一路由)",
        "description": "所有模型通过代理路由，支持 deepseek/agnes/glm 任意切换",
        "type": "proxy",
        "api_key_env": None,
        "env": {
            "ANTHROPIC_AUTH_TOKEN": "proxy-key",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "agnes-2.0-flash",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "agnes-2.0-flash",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "deepseek-v4-pro",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "agnes-2.0-flash",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "agnes-2.0-flash",
            "ANTHROPIC_MODEL": "agnes-2.0-flash",
            "ANTHROPIC_REASONING_MODEL": "agnes-2.0-flash",
        }
    }
}

DIRECT_PROFILES = {"deepseek", "agnes"}


def _resolve_env(profile):
    """将配置中的环境变量占位符替换为实际值"""
    resolved = {**profile}
    resolved["env"] = {**profile["env"]}

    env_var = profile.get("api_key_env")
    if env_var:
        resolved["env"]["ANTHROPIC_AUTH_TOKEN"] = _get_api_key(env_var)

    return resolved


def get_current_profile(settings):
    """检测当前生效的配置"""
    env = settings.get("env", {})
    base_url = env.get("ANTHROPIC_BASE_URL", "")

    if "8030" in base_url:
        model = env.get("ANTHROPIC_MODEL", "")
        if "glm" in model:
            return "glm"
        return "proxy"
    elif "deepseek" in base_url:
        return "deepseek"
    elif "agnes" in base_url or "apihub.agnes" in base_url:
        return "agnes"
    return None


def show_status(settings):
    """显示当前模型状态"""
    env = settings.get("env", {})
    profile = get_current_profile(settings)

    print("=" * 56)
    print("  Claude Code Model Switcher")
    print("=" * 56)

    if profile:
        p = PROFILES[profile]
        tag = "DIRECT" if p["type"] == "direct" else "PROXY"
        key_status = ""
        env_var = p.get("api_key_env")
        if env_var:
            key_status = " ✅" if os.environ.get(env_var) else " ❌ (env not set)"
        print(f"  Active: {p['name']}  [{tag}]{key_status}")
        print(f"  Desc: {p['description']}")
    else:
        print("  Active: Custom (no matching profile)")

    print()
    print("  Key settings:")
    for key in ["ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL"]:
        val = env.get(key, "NOT SET")
        print(f"    {key}")
        print(f"      = {val}")

    print()
    print("  Quick switch:")
    for name, p in sorted(PROFILES.items()):
        tag = "[ACTIVE]" if name == profile else ""
        marker = ">" if name == profile else " "
        env_var = p.get("api_key_env")
        key_ok = os.environ.get(env_var) if env_var else True
        key_mark = "" if key_ok else " ⚠️"
        print(f"    {marker} python switch_model.py {name:10s} -> {p['name']:28s} {tag}{key_mark}")


def switch_to(profile_name, settings):
    """切换到指定配置"""
    if profile_name not in PROFILES:
        print(f"ERROR: Unknown profile: {profile_name}")
        print(f"  Available: {', '.join(PROFILES.keys())}")
        sys.exit(1)

    profile = PROFILES[profile_name]
    old_profile = get_current_profile(settings)

    if old_profile == profile_name:
        print(f"Already on '{profile['name']}'")
        return

    # 检查环境变量
    env_var = profile.get("api_key_env")
    if env_var and not os.environ.get(env_var):
        print(f"  ⚠️  Warning: 环境变量 {env_var} 未设置")
        print(f"     该模型可能无法正常工作")
        print()

    # 解析实际值
    resolved = _resolve_env(profile)

    # 备份当前 env 中需要保留的非模型相关设置
    env = settings.get("env", {})
    preserved = {k: v for k, v in env.items()
                 if not k.startswith("ANTHROPIC_")}

    # 应用新配置
    new_env = {**preserved, **resolved["env"]}
    settings["env"] = new_env

    # 写入文件
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  Switched to {profile['name']}")
    print(f"  Endpoint: {profile['env']['ANTHROPIC_BASE_URL']}")
    print()

    if profile["type"] == "proxy":
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_running = sock.connect_ex(("127.0.0.1", 8030)) == 0
        sock.close()

        if proxy_running:
            print("  Proxy is running on http://127.0.0.1:8030")
        else:
            print("  [!] Proxy is NOT running!")
            print("  Start it in a separate terminal:")
            print(f"    python scripts/lib/model_proxy.py")
            print()
            ans = input("  Start proxy now? [Y/n]: ").strip().lower()
            if ans != "n":
                print("  Starting proxy in background...")
                subprocess.Popen(
                    ["start", "ModelProxy", "python", PROXY_SCRIPT],
                    shell=True,
                )
                print("  Proxy started in new window.")
    else:
        print("  Direct connection - no proxy needed.")

    print()
    print("  Next: run /model sonnet in a new Claude Code session")
    print("  Or restart Claude Code")


def main():
    if not os.path.exists(SETTINGS_PATH):
        print(f"ERROR: settings.json not found: {SETTINGS_PATH}")
        sys.exit(1)

    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    args = sys.argv[1:]

    if not args:
        show_status(settings)
    elif args[0] == "--list":
        print("Available profiles:")
        print(f"  {'Name':12s} {'Mode':8s} {'Key':12s} {'Description'}")
        print(f"  {'-'*12} {'-'*8} {'-'*12} {'-'*30}")
        for name, p in sorted(PROFILES.items()):
            env_var = p.get("api_key_env", "")
            print(f"  {name:12s} {p['type']:8s} {env_var:12s} {p['description']}")
    elif args[0] == "--start-proxy":
        print("Starting proxy in new window...")
        subprocess.Popen(
            ["start", "ModelProxy", "python", PROXY_SCRIPT],
            shell=True,
        )
        print("Done! Proxy started on http://127.0.0.1:8030")
    elif args[0] in PROFILES:
        switch_to(args[0], settings)
    else:
        print(f"ERROR: Unknown command: {args[0]}")
        print(f"  python switch_model.py [deepseek|agnes|glm|proxy|--list]")
        sys.exit(1)


if __name__ == "__main__":
    main()
