$ErrorActionPreference = "Stop"
Set-Location (Split-Path $MyInvocation.MyCommand.Path -Parent)
Set-Location ..

python -m pip install --upgrade pyinstaller cryptography
python -m PyInstaller packaging/CrossMouse.spec --noconfirm --clean

Write-Host "Built: dist/CrossMouse.exe"
