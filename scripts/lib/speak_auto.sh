#!/bin/bash
# Auto-speak: call Windows TTS from WSL
# Usage: speak_auto.sh "text to speak"
powershell.exe -NoProfile -Command "python D:\Reasonix\scripts\lib\speak.py \"$1\"" 2>/dev/null
