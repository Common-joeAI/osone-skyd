# OSONE Hive Node Installer for Windows
# $env:HIVE_TOKEN="yourtoken"; $env:OSONE_URL="https://app.osone.org"; iex (irm https://app.osone.org/agent/install.ps1)

param(
    [string]$OsoneUrl  = $env:OSONE_URL,
    [string]$HiveToken = $env:HIVE_TOKEN,
    [string]$NodeId    = $env:NODE_ID
)
if (-not $OsoneUrl) { $OsoneUrl = "https://app.osone.org" }
if (-not $NodeId)   { $NodeId   = $env:COMPUTERNAME }

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     OSONE Hive Node Installer        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if (-not $HiveToken) {
    Write-Host "[error] HIVE_TOKEN is required." -ForegroundColor Red
    exit 1
}

# Auto-elevate if not admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[!] Relaunching as Administrator..." -ForegroundColor Yellow
    $args2 = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:HIVE_TOKEN='$HiveToken'; `$env:OSONE_URL='$OsoneUrl'; `$env:NODE_ID='$NodeId'; iex (irm '$OsoneUrl/agent/install.ps1')`""
    Start-Process powershell -ArgumentList $args2 -Verb RunAs
    exit
}

# Find Python 3
Write-Host "[+] Checking Python..." -ForegroundColor Green
$python = $null
foreach ($p in @("python", "python3", "py")) {
    try { $v = & $p --version 2>&1; if ($v -match "Python 3") { $python = $p; break } } catch {}
}
if (-not $python) {
    Write-Host "    Python not found — installing Python 3.12 via winget..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $python = "python"
}
$pyver = & $python --version 2>&1
Write-Host "    Using: $python ($pyver)" -ForegroundColor Gray

# Get full python exe path
$pythonExe = (Get-Command $python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) { $pythonExe = $python }

# Bootstrap pip — use ensurepip then upgrade
Write-Host "[+] Ensuring pip..." -ForegroundColor Green
$pipOut = & $pythonExe -m pip --version 2>&1
if ($pipOut -notmatch "pip \d") {
    Write-Host "    Bootstrapping pip via ensurepip..." -ForegroundColor Yellow
    & $pythonExe -m ensurepip --upgrade 2>&1 | Out-Null
    # If ensurepip fails (Python 3.14 may not bundle it), use get-pip.py
    $pipOut2 = & $pythonExe -m pip --version 2>&1
    if ($pipOut2 -notmatch "pip \d") {
        Write-Host "    Falling back to get-pip.py..." -ForegroundColor Yellow
        $getTmp = "$env:TEMP\get-pip.py"
        Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $getTmp -UseBasicParsing
        & $pythonExe $getTmp --quiet
    }
}

# Install deps
Write-Host "[+] Installing dependencies (websockets, psutil)..." -ForegroundColor Green
& $pythonExe -m pip install websockets psutil --quiet --no-warn-script-location

# Create install dir
$installDir = "$env:ProgramData\osone"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

# Download node agent
Write-Host "[+] Downloading node agent..." -ForegroundColor Green
Invoke-WebRequest "$OsoneUrl/agent/node.py" -OutFile "$installDir\node.py" -UseBasicParsing

# Write env config
@"
OSONE_URL=$OsoneUrl
HIVE_TOKEN=$HiveToken
NODE_ID=$NodeId
"@ | Out-File "$installDir\config.env" -Encoding utf8

# Write launcher batch
@"
@echo off
set OSONE_URL=$OsoneUrl
set HIVE_TOKEN=$HiveToken
set NODE_ID=$NodeId
"$pythonExe" "$installDir\node.py"
"@ | Out-File "$installDir\run.bat" -Encoding ascii

# Register scheduled task
Write-Host "[+] Registering startup task as SYSTEM..." -ForegroundColor Green
$taskName = "OSONE-Node"
$action   = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$installDir\node.py`""
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Hours 0)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

# Set env vars at machine level for the task
[System.Environment]::SetEnvironmentVariable("OSONE_URL",  $OsoneUrl,  "Machine")
[System.Environment]::SetEnvironmentVariable("HIVE_TOKEN", $HiveToken, "Machine")
[System.Environment]::SetEnvironmentVariable("NODE_ID",    $NodeId,    "Machine")

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2

$taskInfo = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$taskState = if ($taskInfo) { $taskInfo.State } else { "not found" }

Write-Host ""
Write-Host "✓ OSONE node installed!" -ForegroundColor Green
Write-Host "  Node ID:    $NodeId" -ForegroundColor Cyan
Write-Host "  Commander:  $OsoneUrl" -ForegroundColor Cyan
Write-Host "  Task state: $taskState" -ForegroundColor Cyan
Write-Host "  Files:      $installDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Run manually to see live output:" -ForegroundColor Gray
Write-Host "  $pythonExe $installDir\node.py" -ForegroundColor Gray
