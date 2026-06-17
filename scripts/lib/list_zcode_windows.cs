Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Diagnostics;

public class WinEnum {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
    
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc e, IntPtr p);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder t, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr h, int cmd);
    
    public static List<IntPtr> FindWindowsForProcess(int targetPid) {
        var result = new List<IntPtr>();
        EnumWindows((hwnd, lp) => {
            GetWindowThreadProcessId(hwnd, out uint pid);
            if (pid == targetPid) {
                result.Add(hwnd);
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }
}
"@

$p = Get-Process "ZCode" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Host "ZCode not running"; exit 1 }
$pid = $p.Id

$windows = [WinEnum]::FindWindowsForProcess($pid)
Write-Host "Found $($windows.Count) windows for PID $pid"

foreach ($hwnd in $windows) {
    $sb = New-Object System.Text.StringBuilder 512
    [WinEnum]::GetWindowText($hwnd, $sb, 512)
    $title = $sb.ToString()
    if ($title) {
        Write-Host "  [$($hwnd.ToInt64())] $title"
    }
}
