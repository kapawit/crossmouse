$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $MyInvocation.MyCommand.Path -Parent) -Parent
$exe = Join-Path $root "dist\CrossMouse.exe"

if (-not (Test-Path $exe)) {
    throw "Build first: dist\CrossMouse.exe not found"
}

$installDir = Join-Path $env:LOCALAPPDATA "Programs\CrossMouse"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item -Path $exe -Destination (Join-Path $installDir "CrossMouse.exe") -Force

$shortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\CrossMouse.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $installDir "CrossMouse.exe"
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "CrossMouse - share one mouse and keyboard over LAN"
$shortcut.Save()

Write-Host "Installed: $installDir\CrossMouse.exe"
Write-Host "Start Menu: $shortcutPath"
