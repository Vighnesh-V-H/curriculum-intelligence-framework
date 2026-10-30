# Starts the backend and frontend dev servers in visible console windows.
# Stops any previous instances bound to the ports first.

$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "Frontend"

function Stop-DevProcesses {
    Write-Host "Stopping existing dev servers..."
    Get-CimInstance Win32_Process |
        Where-Object {
            ($_.Name -in @("python.exe", "cmd.exe") -and $_.CommandLine -match [regex]::Escape($backend)) -or
            ($_.Name -in @("node.exe", "cmd.exe") -and $_.CommandLine -match [regex]::Escape($frontend))
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force
        }
    foreach ($port in 8000, 3000) {
        Get-NetTCPConnection -LocalPort $port -State Listen |
            ForEach-Object {
                Stop-Process -Id $_.OwningProcess -Force
            }
    }
    Start-Sleep -Seconds 2
}

function Start-Servers {
    Write-Host "Starting backend on http://127.0.0.1:8000 ..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "title Curriculum Backend && cd /d $backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
    Start-Sleep -Seconds 2

    Write-Host "Starting frontend on http://localhost:3000 ..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "title Curriculum Frontend && cd /d $frontend && npm run dev"
}

function Test-Startup {
    $healthy = $false
    for ($i = 0; $i -lt 15; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
            $healthy = $response.StatusCode -eq 200
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if ($healthy) {
        Write-Host ""
        Write-Host "Backend:  healthy  -> http://127.0.0.1:8000"
        Write-Host "Frontend: starting -> http://localhost:3000"
        Write-Host ""
    } else {
        Write-Warning "Backend did not report healthy within 30 s - check the Curriculum Backend window."
    }
}

Stop-DevProcesses
Start-Servers
Test-Startup
