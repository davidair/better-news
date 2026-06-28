# setup_task.ps1
# Registers a Windows Task Scheduler task that runs the better-news pipeline
# every 2 hours. Run once as Administrator (or as the user who will own the task).
#
# Usage:
#   .\setup_task.ps1 -To your@email.com -Runtime ollama -FeedsFile feeds.yaml
#
# Optional overrides:
#   -IntervalHours 4         (default: 2)
#   -Runtime llama_cpp
#   -DbPath C:\custom\path\rss_storage.sqlite
#   -RawStoragePath C:\custom\path\rss_raw_data

param(
    [Parameter(Mandatory)][string]$To,
    [Parameter(Mandatory)][ValidateSet('ollama','llama_cpp')][string]$Runtime,
    [string]$FeedsFile = 'feeds.yaml',
    [int]$IntervalHours = 2,
    [string]$DbPath = '',
    [string]$RawStoragePath = ''
)

$ErrorActionPreference = 'Stop'

$ProjectDir = $PSScriptRoot
$Python     = Join-Path $ProjectDir '.venv\Scripts\python.exe'
$Script     = Join-Path $ProjectDir 'run_pipeline.py'
$TaskName   = 'BetterNews-Pipeline'

if (-not (Test-Path $Python)) {
    Write-Error "Python venv not found at $Python. Run: python -m venv .venv && pip-sync"
    exit 1
}

if (-not (Test-Path $Script)) {
    Write-Error "run_pipeline.py not found at $Script"
    exit 1
}

# Build argument list
$PipelineArgs = "--feeds-file `"$FeedsFile`" --runtime $Runtime --to `"$To`""
if ($DbPath)         { $PipelineArgs += " --db-path `"$DbPath`"" }
if ($RawStoragePath) { $PipelineArgs += " --raw-storage-path `"$RawStoragePath`"" }

$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "$Script $PipelineArgs" `
    -WorkingDirectory $ProjectDir

# Repeat every N hours, starting now, running indefinitely
$Trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) `
    -Once -At (Get-Date)

# Run only when user is logged in; don't wake the machine
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries

# Remove existing task if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Better News: download RSS feeds, analyze sentiment, send digest" | Out-Null

Write-Host "Task '$TaskName' registered successfully."
Write-Host "  Runs every $IntervalHours hour(s), starting now."
Write-Host "  To remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host "  To run now: Start-ScheduledTask -TaskName '$TaskName'"
