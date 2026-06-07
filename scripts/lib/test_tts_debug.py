"""Debug TTS - test each engine with verbose output"""
import sys, os, time, traceback

# Force SAPI5 test
print("=== SAPI5 Direct Test ===", flush=True)
try:
    import win32com.client
    sp = win32com.client.Dispatch("SAPI.SpVoice")
    
    # List voices
    print(f"Voice count: {sp.GetVoices().Count}", flush=True)
    
    # Try Xiaoxiao
    found = False
    for i in range(sp.GetVoices().Count):
        d = sp.GetVoices().Item(i).GetDescription()
        print(f"  [{i}] {d}", flush=True)
        if "xiaoxiao" in d.lower() and "natural" in d.lower() and "online" not in d.lower():
            sp.Voice = sp.GetVoices().Item(i)
            print(f"  → Selected Xiaoxiao Natural (local)", flush=True)
            found = True
            break
    
    if not found:
        for i in range(sp.GetVoices().Count):
            d = sp.GetVoices().Item(i).GetDescription()
            if "xiaoxiao" in d.lower():
                sp.Voice = sp.GetVoices().Item(i)
                print(f"  → Selected fallback: {d}", flush=True)
                found = True
                break
    
    if not found:
        print("  No Xiaoxiao voice found, using default", flush=True)
    
    # Test synchronous speak
    print("Speaking synchronously...", flush=True)
    sp.Speak("你好小金东，这是SAPI5直接测试", 0)  # SVSFDefault = 0 (sync)
    print("Done speaking!", flush=True)
    
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    traceback.print_exc()
