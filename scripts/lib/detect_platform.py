"""动态检测当前运行平台: Reasonix vs Claude Code

用法:
  python detect_platform.py          # JSON 输出检测结果
  python detect_platform.py --name   # 只输出平台名 (reasonix/claude/unknown)

检测维度 (按可靠性降序):
  1. ~/.claude/shell-snapshots/    → Claude Code 专属 (shell 安全快照)
  2. CLAUDE.md 加载来源            → Claude Code 加载 ~/.claude/CLAUDE.md
  3. .claude/settings.json         → Claude Code 项目配置
  4. reasonix.toml                  → Reasonix 项目配置
  5. 父进程名                      → cowork-svc.exe (Claude) vs reasonix(.exe)
  6. env REASONIX_PLATFORM         → 显式声明
"""

import os, sys, json, subprocess, platform


def detect():
    clues = []
    weights = {}  # platform -> total weight

    def add_clue(platform: str, clue: str, weight: int = 1):
        clues.append({"platform": platform, "clue": clue, "weight": weight})
        weights[platform] = weights.get(platform, 0) + weight

    home = os.path.expanduser("~")
    project = os.getcwd()

    # ── 维度 1: shell-snapshots (Claude Code 专属, 最高权重) ──
    snapshots = os.path.join(home, ".claude", "shell-snapshots")
    if os.path.isdir(snapshots):
        add_clue("claude", f"shell-snapshots 存在 ({len(os.listdir(snapshots))} 个快照)", weight=5)

    # ── 维度 2: ~/.claude/CLAUDE.md (Claude Code 个人指令) ──
    if os.path.isfile(os.path.join(home, ".claude", "CLAUDE.md")):
        add_clue("claude", "~/.claude/CLAUDE.md 存在", weight=3)

    # ── 维度 3: 项目级 .claude/ (Claude Code) vs .reasonix/ (Reasonix) ──
    if os.path.isdir(os.path.join(project, ".claude")):
        if os.path.isfile(os.path.join(project, ".claude", "settings.json")) or \
           os.path.isfile(os.path.join(project, ".claude", "settings.local.json")):
            add_clue("claude", "项目 .claude/settings.json 存在", weight=3)

    if os.path.isdir(os.path.join(project, ".reasonix")):
        add_clue("reasonix", "项目 .reasonix/ 存在", weight=2)

    if os.path.isfile(os.path.join(project, "reasonix.toml")):
        add_clue("reasonix", "项目 reasonix.toml 存在", weight=2)

    # ── 维度 4: 进程检测 ──
    try:
        if platform.system() == "Windows":
            script = f"""
            $claude = Get-CimInstance Win32_Process | Where-Object {{
                $_.Name -match "cowork-svc|claude" -and
                $_.CommandLine -notmatch "powershell|cmd|bash|conhost"
            }} | Select-Object -First 1
            if ($claude) {{ Write-Host "CLAUDE:$($claude.ProcessId)" }}
            $reasonix = Get-CimInstance Win32_Process | Where-Object {{
                $_.Name -match "reasonix" -and
                $_.CommandLine -notmatch "powershell|cmd|bash|conhost|pythonw"
            }} | Select-Object -First 1
            if ($reasonix) {{ Write-Host "REASONIX:$($reasonix.ProcessId)" }}
            """
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("CLAUDE:"):
                    add_clue("claude", f"cowork-svc/claude 进程运行中 PID={line.split(':')[1]}", weight=4)
                elif line.startswith("REASONIX:"):
                    add_clue("reasonix", f"reasonix 进程运行中 PID={line.split(':')[1]}", weight=4)
    except Exception:
        pass

    # ── 维度 5: 环境变量 ──
    for var, platform_name in [("REASONIX_PLATFORM", "reasonix"), ("CLAUDE_CODE", "claude")]:
        val = os.environ.get(var, "")
        if val:
            add_clue(platform_name, f"环境变量 {var}={val}", weight=3)

    # ── 维度 6: CLI 命令可用性 ──
    for cmd, platform_name in [("claude", "claude"), ("reasonix", "reasonix")]:
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                add_clue(platform_name, f"{cmd} CLI 可用: {r.stdout.strip()}", weight=1)
        except:
            pass

    # ── 评分 ──
    score_claude = weights.get("claude", 0)
    score_reasonix = weights.get("reasonix", 0)
    total = score_claude + score_reasonix

    if score_claude > score_reasonix:
        verdict = "claude"
    elif score_reasonix > score_claude:
        verdict = "reasonix"
    else:
        verdict = "unknown"

    return {
        "platform": verdict,
        "score": {"claude": score_claude, "reasonix": score_reasonix},
        "weighted_confidence": max(score_claude, score_reasonix) / max(total, 1),
        "clues": clues,
        "note": "claude=Claude Code CLI | reasonix=Reasonix (桌面版/CLI)"
    }


if __name__ == "__main__":
    result = detect()
    if "--name" in sys.argv:
        print(result["platform"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
