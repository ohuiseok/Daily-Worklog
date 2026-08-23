Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Icon = Join-Path $ProjectRoot "assets\desktop-worklog.ico"

if (!(Test-Path $Python)) {
    throw "Virtual environment Python not found: $Python"
}

if (!(Test-Path $Icon)) {
    throw "Icon file not found: $Icon"
}

& $Python -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --icon $Icon `
    --name desktop-worklog-to-notion `
    (Join-Path $ProjectRoot "desktop_worklog_to_notion.py")

& $Python -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --icon $Icon `
    --name uninstall `
    (Join-Path $ProjectRoot "uninstall_desktop_worklog_to_notion.py")

$Exe = Join-Path $ProjectRoot "dist\desktop-worklog-to-notion.exe"
if (!(Test-Path $Exe)) {
    throw "Build finished but exe was not found: $Exe"
}

$UninstallExe = Join-Path $ProjectRoot "dist\uninstall.exe"
if (!(Test-Path $UninstallExe)) {
    throw "Build finished but uninstall exe was not found: $UninstallExe"
}

Write-Host "Built: $Exe"
Write-Host "Built: $UninstallExe"
