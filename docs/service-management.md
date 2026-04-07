# Service Management

The AI Session Tracker can run as a persistent background service that
survives editor restarts and login sessions.

## Quick Start

```bash
# Install and register the service
ai-session-tracker service install

# Start it now
ai-session-tracker service start

# Check status
ai-session-tracker service status
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `ai-session-tracker service install` | Register auto-start service |
| `ai-session-tracker service start` | Start the service |
| `ai-session-tracker service stop` | Stop the service |
| `ai-session-tracker service status` | Show running state and PIDs |
| `ai-session-tracker service uninstall` | Remove auto-start registration |

## Platform Details

### Linux (systemd)

Installs a user service at `~/.config/systemd/user/ai-session-tracker.service`.

```bash
# Manual management (equivalent to CLI)
systemctl --user status ai-session-tracker
systemctl --user restart ai-session-tracker
journalctl --user -u ai-session-tracker -f  # view logs
```

### macOS (launchd)

Installs a launch agent at `~/Library/LaunchAgents/com.ai-session-tracker.plist`.

```bash
# Manual management
launchctl list | grep ai-session-tracker
```

### Windows (Task Scheduler)

Registers a scheduled task that runs at user logon. A PowerShell management
script is bundled at `scripts/ai-session-tracker.ps1`.

```powershell
# Manual management
.\ai-session-tracker.ps1 start
.\ai-session-tracker.ps1 stop
.\ai-session-tracker.ps1 status
```

## Environment Variables

The service preserves these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_OUTPUT_DIR` | `~/.ai_sessions` | Storage directory for session data |
| `AI_MAX_SESSION_DURATION_HOURS` | `4.0` | Max session duration before auto-close |

Set these in your shell profile before installing the service, or edit the
service unit/task directly after installation.

## Dashboard

When the service is running, the dashboard is available at:

```
http://127.0.0.1:8000
```
