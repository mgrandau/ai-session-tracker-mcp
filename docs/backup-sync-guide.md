# Backup and Sync Guide

## Why the MCP server doesn't own backup

The AI session tracker MCP server writes session data to a single directory — by
default `.ai_sessions/` in your project root, or wherever you point `AI_OUTPUT_DIR`.
That is the full extent of its responsibility.

Backup, sync, and aggregation are intentionally left to the developer. The reasons
are practical:

- **No credentials in the MCP.** The server runs locally and inline with your IDE.
  Embedding AWS keys, OAuth tokens, or SSH credentials in a process that handles
  developer tooling creates unnecessary attack surface. Keeping it out means a
  compromised plugin or dependency can never exfiltrate cloud credentials.

- **You already have sync tools.** OneDrive, Dropbox, rsync, and git are battle-tested
  for exactly this job. Rebuilding any of them inside the MCP would do it worse.

- **Flexibility.** Your team may use OneDrive today and a NAS next year. Swapping
  one cron job or changing `AI_OUTPUT_DIR` is far easier than a server upgrade.

- **Small blast radius.** The worst a misconfigured `AI_OUTPUT_DIR` can do is write
  files to the wrong place. There is no code path that can delete, overwrite, or
  push data somewhere unintended.

The patterns below each follow the same structure: point `AI_OUTPUT_DIR` at the
right place, let the sync tool do the rest.

---

## Pattern 1 — Cloud-synced folder (OneDrive, Dropbox, Google Drive)

This is the easiest option and requires zero scheduled tasks. The sync client
running on your machine monitors the folder and pushes changes automatically.

### Step 1 — Set `AI_OUTPUT_DIR` in your MCP config

The MCP server reads `AI_OUTPUT_DIR` from the `env` block in `.vscode/mcp.json`.
After running `ai-session-tracker install`, open `.vscode/mcp.json` and set the
value:

```jsonc
{
  "servers": {
    "ai-session-tracker": {
      "command": "ai-session-tracker",
      "args": ["server", "--dashboard-host", "127.0.0.1", "--dashboard-port", "8000"],
      "env": {
        "AI_OUTPUT_DIR": "C:\\Users\\jsmith\\OneDrive\\ai-metrics\\my-project",
        "AI_MAX_SESSION_DURATION_HOURS": "4.0"
      }
    }
  }
}
```

> **Why here?** MCP hosts (VS Code, Codex) inject variables from the `env` block
> into the server process. Setting `AI_OUTPUT_DIR` at the system level also works
> (see below), but the `mcp.json` approach is portable, per-project, and
> version-controlled.

### Step 2 — (Optional) Set the environment variable at the OS level

If you prefer a single global setting instead of per-project `mcp.json` config:

**Linux/macOS**

```bash
# ~/.bashrc or ~/.profile
export AI_OUTPUT_DIR=/home/jsmith/OneDrive/ai-metrics/my-project
```

**Windows (PowerShell — runs once, persists across reboots)**

```powershell
[Environment]::SetEnvironmentVariable(
    "AI_OUTPUT_DIR",
    "C:\Users\jsmith\OneDrive\ai-metrics\my-project",
    "User"
)
```

**Windows (System Properties)**

1. Open **Start → Edit the system environment variables**
2. Under **User variables**, click **New**
3. Name: `AI_OUTPUT_DIR` — Value: `C:\Users\jsmith\OneDrive\ai-metrics\my-project`

> ⚠️ **Windows note:** VS Code does not pick up environment variable changes until
> it is fully restarted. Changing a User variable via System Properties or
> PowerShell will not take effect in an already-running VS Code window.

> **Team setup:** Each developer creates a subdirectory named after themselves
> under a shared parent folder (e.g. `OneDrive/ai-metrics/jsmith/`). A
> project lead opens the web dashboard against the parent to see all
> contributors at once.

---

## Pattern 2 — Shared network drive

Useful for on-premises environments (corporate NAS, SMB share, etc.).

**Linux/macOS** — mount the share first, then point `AI_OUTPUT_DIR` at it:

```bash
# /etc/fstab (auto-mount on boot)
//nas.corp.example.com/ai-metrics /mnt/ai-metrics cifs credentials=/etc/samba/creds,uid=jsmith,gid=staff 0 0

# ~/.bashrc
export AI_OUTPUT_DIR=/mnt/ai-metrics/jsmith/my-project
```

**Windows** — map the share as a drive letter:

```powershell
# Map the share (persists until explicitly removed)
New-PSDrive -Name Z -PSProvider FileSystem -Root \\nas.corp.example.com\ai-metrics -Persist

# Set the env var
[Environment]::SetEnvironmentVariable("AI_OUTPUT_DIR", "Z:\jsmith\my-project", "User")
```

---

## Pattern 3 — Git repository

Good for teams that want a full audit trail and the ability to query history.

```bash
# Create a dedicated metrics repo
mkdir ~/team-metrics && cd ~/team-metrics
git init
git remote add origin git@github.com:yourorg/ai-metrics.git

# Point AI_OUTPUT_DIR at a per-developer subdirectory
export AI_OUTPUT_DIR=/home/jsmith/team-metrics/jsmith
```

**Linux/macOS — auto-commit with cron:**

```bash
# crontab -e  (runs every hour)
0 * * * * cd /home/jsmith/team-metrics && git add -A && git commit -m "metrics $(date +\%Y-\%m-\%dT\%H:\%M)" && git push origin main
```

**Windows — auto-commit with Task Scheduler:**

Create `push-metrics.ps1`:

```powershell
Set-Location C:\Users\jsmith\team-metrics
git add -A
git commit -m "metrics $(Get-Date -Format 'yyyy-MM-ddTHH:mm')"
git push origin main
```

Register the task (runs hourly):

```powershell
$action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NonInteractive -File C:\Users\jsmith\push-metrics.ps1"
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At (Get-Date)
Register-ScheduledTask -TaskName "PushAIMetrics" -Action $action -Trigger $trigger -RunLevel Highest
```

---

## Pattern 4 — S3 (or any S3-compatible object store)

The MCP server has no built-in S3 integration. Use `aws s3 sync` on a schedule
instead. This gives you the same result with full control over credentials,
IAM policies, and sync frequency.

**Linux/macOS — cron:**

```bash
# Requires AWS CLI configured: aws configure
# crontab -e  (runs every 30 minutes)
*/30 * * * * aws s3 sync /home/jsmith/.ai_sessions s3://yourorg-ai-metrics/jsmith/my-project --delete
```

**Windows — Task Scheduler:**

Create `sync-to-s3.ps1`:

```powershell
# Requires AWS CLI: https://aws.amazon.com/cli/
aws s3 sync C:\Users\jsmith\.ai_sessions s3://yourorg-ai-metrics/jsmith/my-project --delete
```

Register the task (runs every 30 minutes):

```powershell
$action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NonInteractive -File C:\Users\jsmith\sync-to-s3.ps1"
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 30) -Once -At (Get-Date)
Register-ScheduledTask -TaskName "SyncAIMetricsToS3" -Action $action -Trigger $trigger
```

> You can also use `rclone` in place of `aws s3 sync` to target MinIO, Backblaze B2,
> Google Cloud Storage, or any other S3-compatible store with zero code changes.

---

## Pattern 5 — rsync to a remote server

Minimal footprint, works anywhere SSH is available.

**Linux/macOS — cron:**

```bash
# crontab -e  (runs every hour)
0 * * * * rsync -az --delete /home/jsmith/.ai_sessions/ metrics-server:/var/ai-metrics/jsmith/my-project/
```

**Windows**

Install [cwRsync](https://itefix.net/cwrsync) or use WSL, then schedule the
equivalent command via Task Scheduler as shown in the S3 pattern above.

---

## Choosing a pattern

| Situation | Recommended pattern |
|-----------|-------------------|
| Small team, everyone uses OneDrive/SharePoint | Pattern 1 |
| Corporate environment with NAS | Pattern 2 |
| Want full history and diffs | Pattern 3 (git) |
| Already using AWS | Pattern 4 (S3) |
| Self-hosted Linux infrastructure | Pattern 5 (rsync) |
| Want S3-compatible but not AWS | Pattern 4 with rclone |

All patterns compose. You can use Pattern 1 for day-to-day sync and Pattern 3
to keep a monthly git snapshot, for example.
