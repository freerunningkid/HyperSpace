import json, os

# Create the global settings file with hooks
appdata = os.environ.get('APPDATA', '')
settings_dir = os.path.join(appdata, 'reasonix')
settings_path = os.path.join(settings_dir, 'settings.json')

os.makedirs(settings_dir, exist_ok=True)

hooks = {
    "hooks": {
        "SessionStart": [
            'echo [TTS] 会话开始 > "D:\\Reasonix\\.reasonix\\tts_last.txt" 2>&1'
        ],
        "UserPromptSubmit": [
            'if exist "D:\\Reasonix\\.reasonix\\tts_last.txt" (findstr "未触发" "D:\\Reasonix\\.reasonix\\tts_last.txt" >nul && echo [TTS警告] 上一轮忘了TTS！)'
        ],
        "SessionEnd": [
            'echo [TTS] 记得跑evolve > "D:\\Reasonix\\.reasonix\\tts_guard_end.txt" 2>&1'
        ]
    }
}

with open(settings_path, 'w', encoding='utf-8') as f:
    json.dump(hooks, f, indent=2, ensure_ascii=False)

print(f'Created: {settings_path}')
print(f'Hooks: {", ".join(hooks["hooks"].keys())}')
