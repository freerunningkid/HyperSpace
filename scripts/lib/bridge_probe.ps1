Add-Type -AssemblyName UIAutomationClient

# Find ZCode window via Chrome_WidgetWin_1 class (Electron apps)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string win);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder t, int n);
}
"@

$hwnd = [Win32]::FindWindow("Chrome_WidgetWin_1", $null)
if ($hwnd -eq [IntPtr]::Zero) {
    Write-Host "FAIL: Chrome_WidgetWin_1 not found"
    exit 1
}

Write-Host "OK: ZCode window found: $hwnd"

$el = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)

# Try getting all text elements
$cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Text)
$texts = $el.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
Write-Host "Text elements: $($texts.Count)"

# Try document/chat elements
$docCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Document)
$docs = $el.FindAll([System.Windows.Automation.TreeScope]::Descendants, $docCond)
Write-Host "Document elements: $($docs.Count)"

# Try list items (chat bubbles)
$listCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::ListItem)
$items = $el.FindAll([System.Windows.Automation.TreeScope]::Descendants, $listCond)
Write-Host "List items: $($items.Count)"
foreach ($it in $items) {
    $n = $it.Current.Name
    if ($n -and $n.Length -gt 2) {
        Write-Host "  ITEM: $($n.Substring(0, [Math]::Min(120, $n.Length)))"
    }
}

# Try pane elements
$paneCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Pane)
$panes = $el.FindAll([System.Windows.Automation.TreeScope]::Descendants, $paneCond)
Write-Host "Pane elements: $($panes.Count)"
