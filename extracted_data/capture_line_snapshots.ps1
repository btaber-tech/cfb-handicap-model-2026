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

# Runs one Python step in isolation: stderr can't throw (EAP Continue), the
# full output (including any traceback) is logged, and a failure never stops
# later steps. Before 2026-11-03 the whole run was one try block, so a single
# CFBD hiccup skipped grading/first-TD/Q1/commits and the log kept only the
# word "Traceback".
function Run-Step([string]$script) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & py -3.14 $script --year 2026 2>&1 | ForEach-Object { "$_" } | Out-String
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            Log "STEP FAILED $script (exit $code): $out"
        } else {
            Log "$script output: $out"
        }
    } catch {
        Log "STEP FAILED $script (exception): $($_.Exception.Message)"
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

try {
    Set-Location $scriptDir
    Log "Starting run"

    Run-Step "capture_line_snapshots.py"
    # Build the upcoming week's projections once the SP+ tab is posted (no-op if it exists).
    Run-Step "ensure_week_projections.py"
    # Public betting splits (Action Network) for RLM -- before the scorecard, which reads them.
    Run-Step "capture_public_betting.py"
    Run-Step "build_scorecard.py"
    # First-TD props: build picks once projections exist, then grade finished games.
    Run-Step "build_first_td_picks.py"
    Run-Step "grade_first_td_picks.py"
    # Q1 Edge Board for the upcoming week, then the HTML page.
    Run-Step "build_q1_matchups.py"
    Run-Step "make_q1_page.py"

    Set-Location $repoRoot
    Commit-AndPush @("extracted_data/line_snapshots_2026.csv") "Line snapshot"
    Commit-AndPush @("extracted_data/public_betting_2026.csv") "Public betting snapshot"
    Commit-AndPush @("extracted_data/week*_2026_projections.csv", "extracted_data/week*_2026_fbs_vs_other.csv", "extracted_data/spplus_picks_2026.csv", "extracted_data/in_season_ratings_2026.csv") "Week projections (local build)"
    Commit-AndPush @("extracted_data/season_scorecard_2026.csv") "Scorecard update"
    Commit-AndPush @("extracted_data/first_td_picks_week*_2026.csv", "extracted_data/first_td_scorecard_2026.csv") "First-TD picks update"
    Commit-AndPush @("extracted_data/q1_matchups_week*_2026.csv", "extracted_data/q1_matchups_week*_2026.html") "Q1 Edge Board update"

    Log "Run complete"
}
catch {
    Log "ERROR: $($_.Exception.Message)"
}
