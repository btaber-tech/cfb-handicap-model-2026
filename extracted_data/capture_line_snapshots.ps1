# Scheduled-task wrapper for capture_line_snapshots.py.
# Runs the CFBD line-snapshot capture and commits/pushes any new rows to
# GitHub, from this machine (bypasses the cloud-sandbox git-push block --
# see cfb-handicap-model-2026 memory for why this runs locally instead of
# via a Claude Code cloud routine).
#
# Registered as a Windows Scheduled Task (see setup notes at bottom of
# this file / project memory) to run every 6 hours.

$ErrorActionPreference = "Stop"
$repoRoot = "C:\Users\BenTa\OneDrive\Desktop\College Football"
$scriptDir = Join-Path $repoRoot "extracted_data"
$logFile = Join-Path $scriptDir "capture_line_snapshots.log"

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $logFile -Value $line
}

try {
    Set-Location $scriptDir
    Log "Starting capture run"

    $captureOutput = python capture_line_snapshots.py --year 2026 2>&1 | Out-String
    Log "capture_line_snapshots.py output: $captureOutput"

    Set-Location $repoRoot
    $status = git status --porcelain -- extracted_data/line_snapshots_2026.csv
    if ([string]::IsNullOrWhiteSpace($status)) {
        Log "No changes to commit (script found nothing new, or 'nothing to capture' off-season case)."
    } else {
        git add extracted_data/line_snapshots_2026.csv
        $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm") + " UTC"
        $commitMsg = "Line snapshot $timestamp`n`nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"

        # git writes routine progress info to stderr, which a global
        # $ErrorActionPreference = "Stop" misreads as a terminating error.
        # Run git natively (not via $ErrorActionPreference-sensitive
        # cmdlets) and check $LASTEXITCODE instead of relying on exceptions.
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
    Log "Run complete"
}
catch {
    Log "ERROR: $($_.Exception.Message)"
}
