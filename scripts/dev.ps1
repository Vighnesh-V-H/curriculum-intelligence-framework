# Starts the backend and frontend dev servers in visible console windows.
# Stops any previous instances bound to the ports first.

$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "Frontend"
$script:BackendPort = 8000

function Stop-DevProcesses {
    Write-Host "Stopping existing dev servers..."
    $devProcesses = @(
        Get-CimInstance Win32_Process |
            Where-Object {
                ($_.Name -in @("python.exe", "uv.exe", "uvicorn.exe", "cmd.exe") -and $_.CommandLine -match [regex]::Escape($backend)) -or
                ($_.Name -in @("node.exe", "cmd.exe") -and $_.CommandLine -match [regex]::Escape($frontend))
            }
    )
    $devProcessIds = @($devProcesses | ForEach-Object { $_.ProcessId })
    $devProcessRoots = $devProcesses |
        Where-Object { $_.ParentProcessId -notin $devProcessIds }
    foreach ($process in $devProcessRoots) {
        taskkill.exe /PID $process.ProcessId /T /F | Out-Null
    }
    foreach ($port in 8000, 3000) {
        Get-NetTCPConnection -LocalPort $port -State Listen |
            ForEach-Object {
                Stop-Process -Id $_.OwningProcess -Force
            }
    }
    Start-Sleep -Seconds 2
    while (
        (Get-NetTCPConnection -LocalPort $script:BackendPort -State Listen) -and
        $script:BackendPort -lt 8010
    ) {
        $script:BackendPort++
    }
}

function Start-Servers {
    $apiUrl = "http://127.0.0.1:$script:BackendPort"
    Write-Host "Starting backend on $apiUrl ..."
    $backendCommand = "title Curriculum Backend && cd /d `"$backend`" && uv run uvicorn app.main:app --host 127.0.0.1 --port $script:BackendPort --reload"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $backendCommand
    Start-Sleep -Seconds 2

    Write-Host "Starting frontend on http://localhost:3000 (API: $apiUrl) ..."
    $frontendCommand = "title Curriculum Frontend && cd /d `"$frontend`" && set `"NEXT_PUBLIC_API_URL=$apiUrl`" && npm run dev"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $frontendCommand
}

function Test-Startup {
    $healthy = $false
    for ($i = 0; $i -lt 15; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$script:BackendPort/health" -UseBasicParsing -TimeoutSec 2
            $healthy = $response.StatusCode -eq 200
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if ($healthy) {
        Write-Host ""
        Write-Host "Backend:  healthy  -> http://127.0.0.1:$script:BackendPort"
        Write-Host "Frontend: starting -> http://localhost:3000"
        Write-Host ""
    } else {
        Write-Warning "Backend did not report healthy within 30 s - check the Curriculum Backend window."
    }
}

Stop-DevProcesses
Start-Servers
Test-Startup
