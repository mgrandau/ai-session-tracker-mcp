param(
    [ValidateSet('start', 'stop', 'status')]
    [string]$Action = 'status'
)

# AI Session Tracker MCP Server - Windows Management Script
# This script manages the MCP server process on Windows.
# Bundled with ai-session-tracker-mcp for Task Scheduler integration.

$python = (Get-Command python).Source
$serverArgs = @(
    '-m',
    'ai_session_tracker_mcp',
    'server',
    '--dashboard-host',
    '127.0.0.1',
    '--dashboard-port',
    '8000'
)

function Get-ServerProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'python.exe' -and
        $_.CommandLine -match 'ai_session_tracker_mcp' -and
        $_.CommandLine -match '\sserver\s' -and
        $_.CommandLine -match '--dashboard-port 8000'
    }
}

function Get-DashboardProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'python.exe' -and
        $_.CommandLine -match 'ai_session_tracker_mcp' -and
        $_.CommandLine -match '\sdashboard\s' -and
        $_.CommandLine -match '--port 8000'
    }
}

function Get-AllTrackedProcesses {
    @(
        Get-ServerProcesses
        Get-DashboardProcesses
    ) | Sort-Object ProcessId -Unique
}

switch ($Action) {
    'start' {
        $u = [Environment]::GetEnvironmentVariable('AI_OUTPUT_DIR', 'User')
        if ($u) {
            $env:AI_OUTPUT_DIR = $u
        }

        $env:AI_MAX_SESSION_DURATION_HOURS = '4.0'

        $existing = @(Get-AllTrackedProcesses)
        if ($existing) {
            Write-Output ('already-running:' + (($existing | ForEach-Object { $_.ProcessId }) -join ','))
            return
        }

        $process = Start-Process -FilePath $python -ArgumentList $serverArgs -WindowStyle Hidden -PassThru
        Write-Output "started:$($process.Id)"
    }
    'stop' {
        $tracked = @(Get-AllTrackedProcesses)
        if (-not $tracked) {
            Write-Output 'not-running'
            return
        }

        foreach ($process in $tracked) {
            Stop-Process -Id $process.ProcessId -Force
        }

        Write-Output ('stopped:' + (($tracked | ForEach-Object { $_.ProcessId }) -join ','))
    }
    'status' {
        $servers = @(Get-ServerProcesses)
        $dashboards = @(Get-DashboardProcesses)
        if (-not $servers -and -not $dashboards) {
            Write-Output 'stopped'
            return
        }

        $parts = @()
        if ($servers) {
            $parts += 'server=' + (($servers | ForEach-Object { $_.ProcessId }) -join ',')
        }
        if ($dashboards) {
            $parts += 'dashboard=' + (($dashboards | ForEach-Object { $_.ProcessId }) -join ',')
        }

        Write-Output ('running:' + ($parts -join ';'))
    }
}
