# Set up Seven on a laptop (Ray, 2026-11-04). Run it on the LAPTOP, in PowerShell:
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File laptop-setup.ps1
#   ... -DryRun                       only say what it would do, change nothing
#   ... -DesktopOllama http://DESKTOP:11434   Seven's main model (seven-v33) is used from the desktop's Ollama
#   ... -SkipPython | -SkipOllama | -SkipHindsight   leave one part out
#   ... -HindsightPort N -PostgresPort N -HindsightOllama URL   Hindsight's ports (8890, 5440) and the Ollama it reads its small models from
#   ... -Dir C:\Somewhere             where the repo goes (default D:\Ray-Code if the laptop has a D: drive, else ~\Ray-Code)
#   ... -AllowPush                    leave git push enabled (default: the laptop clone is READ-ONLY, see below)
#
# What it does, in order. Every step can be run again: the script only does what is not done yet.
#   1. Checks Git, Python 3.12, GitHub CLI (and Ollama) and installs what is missing with winget.
#   2. Logs in to GitHub (a browser window opens) and checks the account can read r-anthony-graves/ray-code.
#   3. Clones that repo, or brings an existing clone up to date (fast-forward only). The desktop's own sync script
#      (seven\scripts\sync-to-github.ps1) is what puts the desktop's committed work there; run it on the desktop ("push")
#      for new work to show up here. The laptop clone has its push turned off so it cannot fork that history.
#   4. Makes seven\.venv and installs Seven's packages from seven\requirements.lock.
#   5. Ollama: builds seven-qwythos (Seven's default model, pulled from Hugging Face, about 6.5 GB) and the two CPU-only
#      models Hindsight uses (qwen3-1.7b-cpu, nomic-embed-cpu).
#   6. Hindsight (Seven's memory): installs it in ~\hindsight with its own Postgres (port 5440) and API (127.0.0.1:8890),
#      and creates the bank "ray". The memory starts EMPTY: the desktop's memories are not copied.
#   7. With -DesktopOllama: points Seven at the desktop's Ollama (user environment variables SEVEN_OLLAMA_URL, SEVEN_BASE_URL,
#      SEVEN_MODEL=seven-v33). seven-v33 only exists as a file on the desktop, so this is the way to use it from the laptop.
#
# NOT included: the desktop's Hindsight memories, the OANDA keys, the voiceprint, seven\state and anything else that is not
# committed (for example the qvm archives in sevenfiles\qvm). Copy those by hand if you want them.
param(
    [string]$Dir = $(if (Test-Path -LiteralPath 'D:\') { 'D:\Ray-Code' } else { Join-Path $HOME 'Ray-Code' }),
    [string]$RepoUrl = 'https://github.com/r-anthony-graves/ray-code.git',
    [string]$HindsightDir = (Join-Path $HOME 'hindsight'),
    [string]$DesktopOllama = '',
    [string]$HindsightOllama = '',          # the Ollama Hindsight's two small models are read from (default: this laptop's, or the desktop's with -SkipOllama -DesktopOllama)
    [int]$HindsightPort = 8890,
    [int]$PostgresPort = 5440,
    [switch]$SkipPython, [switch]$SkipOllama, [switch]$SkipHindsight,
    [switch]$NoInstall, [switch]$AllowPush, [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Notes = New-Object System.Collections.Generic.List[string]

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Say($text) { Write-Host "  $text" }
function Warn($text) { Write-Host "  NOTE: $text" -ForegroundColor Yellow; $Notes.Add($text) }
function Fail($text) { Write-Host "STOPPED: $text" -ForegroundColor Red; exit 1 }
function Have($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') }

# A native program: its stderr lines are plain text (Windows PowerShell 5.1 turns them into errors otherwise) and only its
# exit code decides. Returns the exit code; -Quiet hides the output. Under -DryRun it only says what it would run.
function Native([string]$What, [scriptblock]$Cmd, [switch]$Quiet, [switch]$Soft) {
    if ($DryRun) { Say "[dry run] $What"; return 0 }
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try {
        $out = & $Cmd 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { "$_" } }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    if (-not $Quiet) { $out | ForEach-Object { Write-Host "    $_" } }
    if ($code -ne 0 -and -not $Soft) { Fail "$What failed (exit code $code)" }
    return $code
}

function Ensure-Tool([string]$Cmd, [string]$WingetId, [string]$Label) {
    if (Have $Cmd) { Say "$Label : found"; return }
    if ($NoInstall) { Fail "$Label is not installed and -NoInstall was given: install it, then run this again" }
    if (-not (Have 'winget')) { Fail "$Label is not installed and winget is not available: install $Label by hand, then run this again" }
    Say "$Label : not found, installing with winget"
    Native "install $Label" { winget install --id $WingetId -e --accept-package-agreements --accept-source-agreements } | Out-Null
    Refresh-Path
    if (-not $DryRun -and -not (Have $Cmd)) { Fail "$Label was installed but this window cannot see it yet: close this window, open a new PowerShell and run the script again" }
}

function Find-Python312 {
    if (Have 'py') {
        $p = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $p) { return "$p".Trim() }
    }
    return $null
}

if ($DryRun) { Write-Host "DRY RUN: nothing will be changed." -ForegroundColor Yellow }
$viaGithub = $RepoUrl -match 'github\.com'

# ---- 1. tools
Step "1. Tools"
Ensure-Tool 'git' 'Git.Git' 'Git'
if ($viaGithub) { Ensure-Tool 'gh' 'GitHub.cli' 'GitHub CLI' }
$py = $null
if (-not $SkipPython -or -not $SkipHindsight) {          # Hindsight has its own venv, so it needs Python 3.12 too
    $py = Find-Python312
    if (-not $py) {
        if ($NoInstall) { Fail "Python 3.12 is not installed and -NoInstall was given" }
        if (-not (Have 'winget')) { Fail "Python 3.12 is not installed and winget is not available: install it from python.org, then run this again" }
        Say "Python 3.12 : not found, installing with winget"
        Native "install Python 3.12" { winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements } | Out-Null
        Refresh-Path
        $py = Find-Python312
        if (-not $DryRun -and -not $py) { Fail "Python 3.12 was installed but this window cannot see it yet: close this window, open a new PowerShell and run the script again" }
    } else { Say "Python 3.12 : $py" }
}
if (-not $SkipOllama) { Ensure-Tool 'ollama' 'Ollama.Ollama' 'Ollama' }

# ---- 2. GitHub login
Step "2. GitHub"
if ($viaGithub) {
    $code = Native "check the GitHub login" { gh auth status } -Quiet -Soft
    if ($code -ne 0) {
        Say "Not logged in: a browser window opens; log in as the account that owns r-anthony-graves/ray-code."
        Native "log in to GitHub" { gh auth login --web --git-protocol https } | Out-Null
    } else { Say "gh is logged in" }
    Native "let git use the GitHub login" { gh auth setup-git } -Quiet | Out-Null
    $code = Native "check the account can read ray-code" { gh repo view r-anthony-graves/ray-code --json name } -Quiet -Soft
    if ($code -ne 0) { Fail "this GitHub account cannot read r-anthony-graves/ray-code. Run 'gh auth logout' and then this script again, and log in as the account that owns it (you have two accounts)" }
    Say "ray-code is readable"
} else { Say "RepoUrl is not on GitHub ($RepoUrl): no login needed" }

# ---- 3. the repo
Step "3. The repo in $Dir"
if (Test-Path -LiteralPath (Join-Path $Dir '.git')) {
    $origin = (& git -C $Dir remote get-url origin 2>$null)
    if ("$origin".Trim() -ne $RepoUrl) { Fail "${Dir} is a git repository whose origin is '$origin', not ${RepoUrl}: choose another -Dir" }
    $dirty = @(& git -C $Dir status --porcelain --untracked-files=no).Count
    if ($dirty -gt 0) { Fail "$Dir has $dirty changed file(s) of its own: undo them (git -C $Dir restore .) or choose another -Dir, then run this again" }
    Native "fetch" { git -C $Dir fetch origin } | Out-Null
    Native "switch to main" { git -C $Dir checkout main } -Quiet | Out-Null
    $code = Native "bring main up to date" { git -C $Dir merge --ff-only origin/main } -Soft
    if ($code -ne 0) { Fail "main cannot be fast-forwarded. GitHub's main was rewritten or this clone has commits of its own. If the clone holds nothing you want: git -C $Dir reset --hard origin/main" }
} else {
    if ((Test-Path -LiteralPath $Dir) -and @(Get-ChildItem -LiteralPath $Dir -Force).Count -gt 0) { Fail "$Dir exists and is not empty: choose another -Dir" }
    Say "Cloning (a few hundred MB)"
    Native "clone $RepoUrl" { git -c core.longpaths=true clone $RepoUrl $Dir } | Out-Null
}
if (-not $DryRun) {
    Native "long paths on" { git -C $Dir config core.longpaths true } -Quiet | Out-Null
    if (-not $AllowPush) {
        Native "turn push off" { git -C $Dir remote set-url --push origin 'push-disabled-on-the-laptop' } -Quiet | Out-Null
        Say "push is OFF in this clone (the desktop's sync script owns GitHub main); -AllowPush leaves it on"
    }
    $head = (& git -C $Dir rev-parse --short HEAD).Trim()
    Say "main is at $head"
}
if (-not $DryRun -and $Dir -notlike 'D:\*') {
    Warn "Seven's settings default to folders under D:\Ray-Code (for example the office, board, council and web folders). This laptop's repo is in $Dir, so set the matching SEVEN_* environment variables (see seven\seven\config.py), or give the laptop a D: drive and run again with -Dir D:\Ray-Code."
}

# ---- 4. Python
$SevenDir = Join-Path $Dir 'seven'
$VenvPy = Join-Path $SevenDir '.venv\Scripts\python.exe'
Step "4. Seven's Python packages"
if ($SkipPython) { Say "skipped (-SkipPython)" }
else {
    if (-not (Test-Path -LiteralPath $VenvPy)) { Native "make seven\.venv" { & $py -m venv (Join-Path $SevenDir '.venv') } | Out-Null }
    else { Say "seven\.venv exists" }
    Native "update pip" { & $VenvPy -m pip install --upgrade pip } -Quiet | Out-Null
    Say "Installing the packages (several minutes the first time)"
    Native "install requirements.lock" { & $VenvPy -m pip install -r (Join-Path $SevenDir 'requirements.lock') } -Quiet | Out-Null
    Native "install Seven itself" { & $VenvPy -m pip install -e $SevenDir --no-deps } -Quiet | Out-Null
    $code = Native "check Seven imports" { & $VenvPy -c "import seven, seven.forex, seven.council; print('seven imports')" } -Soft
    if ($code -ne 0) { Warn "the packages installed but Seven does not import; run $VenvPy -c 'import seven' to see why" }
}

# ---- 5. Ollama
Step "5. Ollama models"
$OllamaUrl = 'http://127.0.0.1:11434'
if ($SkipOllama) { Say "skipped (-SkipOllama)" }
else {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) 'seven-modelfiles'
    if (-not $DryRun) { New-Item -ItemType Directory -Force $tmp | Out-Null }
    $have = ''
    if (-not $DryRun) { $have = (& ollama list 2>$null) -join "`n" }
    function Model-Present([string]$name) { return ($have -match "(?m)^$([regex]::Escape($name))(:latest)?\s") }

    $cpu = @(
        @{ name = 'qwen3-1.7b-cpu';   from = 'qwen3:1.7b';        ctx = 16384 },
        @{ name = 'nomic-embed-cpu';  from = 'nomic-embed-text';  ctx = 0 }
    )
    foreach ($m in $cpu) {
        if (Model-Present $m.name) { Say "$($m.name) : present"; continue }
        Native "pull $($m.from)" { ollama pull $m.from } | Out-Null
        $body = "FROM $($m.from)`nPARAMETER num_gpu 0`n"
        if ($m.ctx -gt 0) { $body += "PARAMETER num_ctx $($m.ctx)`n" }
        $file = Join-Path $tmp "$($m.name).Modelfile"
        if (-not $DryRun) { [IO.File]::WriteAllText($file, $body, (New-Object Text.UTF8Encoding($false))) }
        Native "build $($m.name)" { ollama create $m.name -f $file } | Out-Null
    }
    if (Model-Present 'seven-qwythos') { Say "seven-qwythos : present" }
    else {
        $mf = Join-Path $SevenDir 'ollama\seven-qwythos.Modelfile'
        if (-not $DryRun -and -not (Test-Path -LiteralPath $mf)) { Fail "$mf is missing: the repo is incomplete" }
        $from = 'hf.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q4_K_M'
        Say "Downloading Seven's model (about 6.5 GB)"
        Native "pull the model from Hugging Face" { ollama pull $from } | Out-Null
        Native "build seven-qwythos" { ollama create seven-qwythos -f $mf } | Out-Null
    }
    Warn "The desktop runs seven-v33, a trained model that only exists as a file on the desktop. This laptop gets seven-qwythos (Seven's default). Use -DesktopOllama to use seven-v33 from the desktop."
}

# ---- 6. Hindsight
Step "6. Hindsight (memory, starts empty)"
if ($SkipHindsight) { Say "skipped (-SkipHindsight)" }
else {
    $hvenv = Join-Path $HindsightDir '.venv'
    $hpy = Join-Path $hvenv 'Scripts\python.exe'
    $data = Join-Path $HindsightDir 'pgdata'
    $logs = Join-Path $HindsightDir 'logs'
    if (-not $DryRun) { New-Item -ItemType Directory -Force $HindsightDir, $logs | Out-Null }
    $hOllama = $OllamaUrl
    if ($HindsightOllama) { $hOllama = $HindsightOllama.TrimEnd('/') }
    elseif ($SkipOllama -and $DesktopOllama) { $hOllama = $DesktopOllama.TrimEnd('/') }
    elseif ($SkipOllama) { Warn "Hindsight needs its two small models (qwen3-1.7b-cpu, nomic-embed-cpu) from an Ollama; with -SkipOllama and no -DesktopOllama it will not start until one answers at $OllamaUrl." }

    if (-not (Test-Path -LiteralPath $hpy)) { Native "make Hindsight's venv" { & $py -m venv $hvenv } | Out-Null } else { Say "Hindsight venv exists" }
    Say "Installing Hindsight 0.10.2 and its Postgres (a few minutes)"
    Native "install Hindsight" { & $hpy -m pip install hindsight-api-slim==0.10.2 hindsight-client==0.10.2 embedded-postgres==18.6.3 httpx } -Quiet | Out-Null
    $pgbin = Join-Path $hvenv 'Lib\site-packages\embedded_postgres\pginstall\bin'

    if (-not $DryRun -and -not (Test-Path -LiteralPath (Join-Path $data 'PG_VERSION'))) {
        Native "make the database folder" { & (Join-Path $pgbin 'initdb.exe') -D $data -U hindsight --auth=trust -E UTF8 } -Quiet | Out-Null
    } else { Say "database folder exists" }

    # the same files the desktop uses, with this machine's folders
    $envFile = Join-Path $HindsightDir 'hindsight.env.ps1'
    $startFile = Join-Path $HindsightDir 'start_hindsight.ps1'
    $bankFile = Join-Path $HindsightDir 'setup_bank.py'
    $envText = @"
# Hindsight 0.10.2 settings (one place). Dot-source before starting the API. Written by laptop-setup.ps1.
`$env:PYTHONUTF8 = '1'; `$env:PYTHONIOENCODING = 'utf-8'
`$env:HINDSIGHT_API_HOST = '127.0.0.1'
`$env:HINDSIGHT_API_PORT = '$HindsightPort'
`$env:HINDSIGHT_API_DATABASE_URL = 'postgresql://hindsight@127.0.0.1:$PostgresPort/hindsight'
`$env:HINDSIGHT_API_LLM_PROVIDER = 'ollama'
`$env:HINDSIGHT_API_LLM_BASE_URL = '$hOllama/v1'
`$env:HINDSIGHT_API_LLM_MODEL = 'qwen3-1.7b-cpu'
`$env:HINDSIGHT_API_EMBEDDINGS_PROVIDER = 'openai'
`$env:HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL = '$hOllama/v1'
`$env:HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL = 'nomic-embed-cpu'
`$env:HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY = 'ollama'
`$env:HINDSIGHT_API_RERANKER_PROVIDER = 'rrf'
Remove-Item Env:LLM_BASE_URL, Env:LLM_MODEL -ErrorAction SilentlyContinue
"@
    $startText = @"
# Start Hindsight's Postgres (port $PostgresPort) and API (127.0.0.1:$HindsightPort). Safe to run twice. Written by laptop-setup.ps1.
`$root = '$HindsightDir'; `$data = '$data'; `$pgbin = '$pgbin'
if (Get-NetTCPConnection -LocalPort $HindsightPort -State Listen -ErrorAction SilentlyContinue) { exit 0 }
& "`$pgbin\pg_ctl.exe" status -D `$data *> `$null
if (`$LASTEXITCODE -ne 0) {
    & "`$pgbin\pg_ctl.exe" start -w -D `$data -o "-p $PostgresPort -c listen_addresses=127.0.0.1" -l "`$root\logs\postgres.log"
    if (`$LASTEXITCODE -ne 0) { exit 1 }
}
. "`$root\hindsight.env.ps1"
for (`$i = 0; `$i -lt 60; `$i++) {
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 '$hOllama/api/tags' | Out-Null; break } catch { Start-Sleep -Seconds 5 }
}
& "`$root\.venv\Scripts\hindsight-api.exe" 2>&1 | ForEach-Object { "`$_" } | Out-File -Append -Encoding utf8 "`$root\logs\api.log"
"@
    $bankText = @'
"""Create/refresh bank 'ray' (config only). Idempotent."""
import sys
import httpx
B = "http://127.0.0.1:8890/v1/default/banks/ray"
httpx.put(B, json={
    "retain_mission": "These are conversations between Ray and his assistant Seven. Keep what Ray said, decided, "
                      "asked for and prefers, with dates. Do not turn the assistant's descriptions of emails, web "
                      "pages or files into facts about Ray.",
    "reflect_mission": "Answer from what Ray actually said. Say when something is not in memory.",
    "retain_extraction_mode": "concise", "enable_observations": True}, timeout=60).raise_for_status()
cfg = httpx.get(f"{B}/config", timeout=60).json()["config"]
print(cfg)
if cfg.get("retain_extraction_mode") != "concise" or cfg.get("enable_observations") is not True:
    sys.exit(1)
'@
    if (-not $DryRun) {
        $utf8 = New-Object Text.UTF8Encoding($true)       # with a BOM: Windows PowerShell 5.1 reads a .ps1 without one as ANSI
        [IO.File]::WriteAllText($envFile, $envText, $utf8)
        [IO.File]::WriteAllText($startFile, $startText, $utf8)
        [IO.File]::WriteAllText($bankFile, $bankText, (New-Object Text.UTF8Encoding($false)))
    }
    Say "wrote start_hindsight.ps1, hindsight.env.ps1 and setup_bank.py in $HindsightDir"

    # the database and the vector extension, then the API
    Native "start Postgres" { & (Join-Path $pgbin 'pg_ctl.exe') start -w -D $data -o "-p $PostgresPort -c listen_addresses=127.0.0.1" -l (Join-Path $logs 'postgres.log') } -Quiet -Soft | Out-Null
    $c = Native "make the database" { & (Join-Path $pgbin 'createdb.exe') -h 127.0.0.1 -p $PostgresPort -U hindsight hindsight } -Quiet -Soft
    if ($c -eq 0) { Say "database 'hindsight' made" }
    Native "pgvector on" { & (Join-Path $pgbin 'psql.exe') -h 127.0.0.1 -p $PostgresPort -U hindsight -d hindsight -c "CREATE EXTENSION IF NOT EXISTS vector" } -Quiet | Out-Null
    if (-not $DryRun) {
        Start-Process -WindowStyle Hidden -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $startFile)
        Say "waiting for Hindsight's API (up to 3 minutes)"
        $up = $false
        for ($i = 0; $i -lt 36 -and -not $up; $i++) {
            try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://127.0.0.1:$HindsightPort/health" | Out-Null; $up = $true } catch { Start-Sleep -Seconds 5 }
        }
        if (-not $up) { Warn "Hindsight's API did not answer in 3 minutes: read $logs\api.log. The most common cause is Ollama not answering at $hOllama yet." }
        else {
            $c = Native "make the bank 'ray'" { & $hpy $bankFile } -Soft
            if ($c -eq 0) { Say "Hindsight is up with an empty bank 'ray'" } else { Warn "Hindsight is up but the bank 'ray' was not set (run: $hpy $bankFile)" }
        }
    }
    # the desktop starts it at logon with a scheduled task
    $hasTask = $false
    if (-not $DryRun) { $hasTask = [bool](Get-ScheduledTask -TaskName 'hindsight' -ErrorAction SilentlyContinue) }
    if (-not $hasTask) {
        if ($DryRun) { Say "[dry run] register the logon task 'hindsight'" }
        else {
            try {
                $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startFile`""
                Register-ScheduledTask -TaskName 'hindsight' -Action $action -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) -Description 'Starts Hindsight at logon (laptop-setup.ps1)' | Out-Null
                Say "logon task 'hindsight' registered"
            } catch { Warn "could not register the logon task ($($_.Exception.Message)); start Hindsight by hand with: powershell -File $startFile" }
        }
    }
    # Seven finds Hindsight at SEVEN_HINDSIGHT_URL, default http://127.0.0.1:8890: nothing to set.
}

# ---- 7. the desktop's Ollama
Step "7. The desktop's Ollama"
if (-not $DesktopOllama) { Say "not asked for (-DesktopOllama); Seven uses this laptop's Ollama" }
else {
    $u = $DesktopOllama.TrimEnd('/')
    $reach = $false
    if (-not $DryRun) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "$u/api/tags" | Out-Null; $reach = $true } catch { } }
    if (-not $DryRun -and -not $reach) {
        Warn "$u does not answer from here. On the DESKTOP, Ollama must listen on the network and Windows Firewall must allow port 11434: set the user environment variable OLLAMA_HOST=0.0.0.0, quit and start Ollama again, and run (as administrator) New-NetFirewallRule -DisplayName 'Ollama LAN' -Direction Inbound -LocalPort 11434 -Protocol TCP -Action Allow -Profile Private. The settings below are saved anyway."
    }
    if ($DryRun) { Say "[dry run] set SEVEN_OLLAMA_URL=$u, SEVEN_BASE_URL=$u/v1, SEVEN_MODEL=seven-v33 for this user" }
    else {
        [Environment]::SetEnvironmentVariable('SEVEN_OLLAMA_URL', $u, 'User')
        [Environment]::SetEnvironmentVariable('SEVEN_BASE_URL', "$u/v1", 'User')
        [Environment]::SetEnvironmentVariable('SEVEN_MODEL', 'seven-v33', 'User')
        Say "set SEVEN_OLLAMA_URL, SEVEN_BASE_URL and SEVEN_MODEL=seven-v33 for this user (new windows see them)"
    }
}

# ---- done
Step "Done"
Say "Repo:        $Dir"
if (-not $SkipPython) { Say "Seven:       $VenvPy" }
if (-not $SkipHindsight) { Say "Hindsight:   http://127.0.0.1:$HindsightPort/health   (folder $HindsightDir)" }
Say "Update:      run this script again, or: git -C $Dir pull --ff-only   (only work the desktop has synced to GitHub shows up)"
Say "Open Seven:  $(Join-Path $SevenDir '.venv\Scripts\seven-window.exe')"
if ($Notes.Count -gt 0) {
    Write-Host ""; Write-Host "Things to know:" -ForegroundColor Yellow
    $n = 1; foreach ($t in $Notes) { Write-Host "  $n. $t"; $n++ }
}
