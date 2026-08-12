# Scheduled-task wrapper: line-snapshot capture + results scorecard.
# Runs both CFBD-dependent steps and commits/pushes any changes to
# GitHub, from this machine (bypasses the cloud-sandbox git-push block --
# see cfb-handicap-model-2026 memory for why this runs locally instead of
# via a Claude Code cloud routine; the weekly projections/artifact
# routine is unaffected and stays in the cloud since it doesn't need to
# push).
#
# Registered as a Windows Scheduled Task "CFB Line Snapshot Capture"
# to run every 6 hours.

$ErrorActionPreference = "Stop"
$repoRoot = "C:\Users\BenTa\OneDrive\Desktop\College Football"
$scriptDir = Join-Path $repoRoot "extracted_data"
$logFile = Join-Path $scriptDir "capture_line_snapshots.log"

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $logFile -Value $line
}

# Commits+pushes the given path(s) if they have changes. git writes
# routine progress info to stderr, which a global
# $ErrorActionPreference = "Stop" misreads as a terminating error, so
# this runs git natively and checks $LASTEXITCODE instead of relying on
# exceptions.
function Commit-AndPush([string[]]$paths, [string]$summary) {
    $status = git status --porcelain -- @paths
    if ([string]::IsNullOrWhiteSpace($status)) {
        Log "No changes to commit for: $($paths -join ', ')"
        return
    }
    git add @paths
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm") + " UTC"
    $commitMsg = "$summary $timestamp`n`nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $commitOutput = git commit -m $commitMsg 2>&1 | Out-String
    Log "git commit output: $commitOutput (exit $LASTEXITCODE)"
    $pushOutput = git push 2>&1 | Out-String
    Log "git push output: $pushOutput (exit $LASTEXITCODE)"
    $ErrorActionPreference = $prevEap
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: git push exited non-zero -- check output above"
    }
}

try {
    Set-Location $scriptDir
    Log "Starting run"

    $captureOutput = python capture_line_snapshots.py --year 2026 2>&1 | Out-String
    Log "capture_line_snapshots.py output: $captureOutput"

    $scorecardOutput = python build_scorecard.py --year 2026 2>&1 | Out-String
    Log "build_scorecard.py output: $scorecardOutput"

    Set-Location $repoRoot
    Commit-AndPush @("extracted_data/line_snapshots_2026.csv") "Line snapshot"
    Commit-AndPush @("extracted_data/season_scorecard_2026.csv") "Scorecard update"

    Log "Run complete"
}
catch {
    Log "ERROR: $($_.Exception.Message)"
}
