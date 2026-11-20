$ErrorActionPreference = "Stop"
Set-Location (Split-Path $MyInvocation.MyCommand.Path -Parent)
Set-Location ..

python -m pip install --upgrade pyinstaller -r requirements.txt
python -m PyInstaller packaging/CrossMouse.spec --noconfirm --clean

Write-Host "Built: dist/CrossMouse.exe"
