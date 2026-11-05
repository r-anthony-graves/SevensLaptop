# Check that Seven is set up properly on THIS machine (Ray, 2026-11-04). Written for the laptop, but it runs anywhere Seven is installed.
# It only READS: no file, variable, shortcut or task is changed, and no key or password is ever printed (only whether a key is set and
# how long it is). The one thing it writes is git's own remote-tracking refs, through `git fetch`; use -NoFetch to skip even that.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File laptop-check.ps1
#   ... -Dir C:\Somewhere\Ray-Code      the repo (default: the repo this script is in)
#   ... -HindsightDir C:\Users\me\hindsight
#   ... -OnDesktop                      the desktop's own run: skips the checks that only make sense on the laptop
#   ... -NoFetch                        do not contact GitHub
#
# Each line starts with PASS, WARN or FAIL. FAIL = something that should work does not. WARN = worth a look, Seven still runs. The last
# line is the count, and the exit code is 1 when anything FAILED. The text after "fix:" says what to run.
param(
    [string]$Dir = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$HindsightDir = (Join-Path $HOME 'hindsight'),
    [switch]$OnDesktop, [switch]$NoFetch
)
$ErrorActionPreference = 'Continue'
$script:pass = 0; $script:warn = 0; $script:fail = 0
function Pass($what, $detail = '') { $script:pass++; Write-Host ("  PASS  {0}{1}" -f $what, $(if ($detail) { "  ($detail)" })) -ForegroundColor Green }
function Warn($what, $fix = '') { $script:warn++; Write-Host ("  WARN  {0}{1}" -f $what, $(if ($fix) { "   fix: $fix" })) -ForegroundColor Yellow }
function Fail($what, $fix = '') { $script:fail++; Write-Host ("  FAIL  {0}{1}" -f $what, $(if ($fix) { "   fix: $fix" })) -ForegroundColor Red }
function Head($t) { Write-Host ""; Write-Host $t -ForegroundColor Cyan }
function Have($n) { [bool](Get-Command $n -ErrorAction SilentlyContinue) }
function Gx { $o = & git -C $Dir @args 2>&1 | ForEach-Object { "$_" }; $script:GitCode = $LASTEXITCODE; $o }
function UserVar($n) { $v = [Environment]::GetEnvironmentVariable($n, 'User'); if (-not $v) { $v = [Environment]::GetEnvironmentVariable($n, 'Process') }; $v }
$Seven = Join-Path $Dir 'seven'
$Venv = Join-Path $Seven '.venv\Scripts\python.exe'

Head "1. This machine"
Pass "$([Environment]::OSVersion.VersionString), PowerShell $($PSVersionTable.PSVersion)"
try { $free = [math]::Round((Get-PSDrive -Name (Split-Path -Qualifier $Dir).TrimEnd(':')).Free / 1GB); if ($free -lt 20) { Warn "only $free GB free on the repo's drive" "free some space (the models alone are about 7 GB)" } else { Pass "$free GB free on the repo's drive" } } catch { }

Head "2. Tools"
if (Have git) { Pass "git" } else { Fail "git is not installed" "winget install --id Git.Git -e" }
$py = $null; if (Have py) { $py = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null); if ($LASTEXITCODE -ne 0) { $py = $null } }
if ($py) { Pass "Python 3.12" "$py" } else { Fail "Python 3.12 is not installed" "winget install --id Python.Python.3.12 -e" }
if (-not $OnDesktop) {
    if (Have gh) { & gh auth status *> $null; if ($LASTEXITCODE -eq 0) { Pass "GitHub CLI, logged in" } else { Warn "GitHub CLI is not logged in" "gh auth login --web --git-protocol https (as the account that owns ray-code)" } } else { Warn "GitHub CLI is not installed" "winget install --id GitHub.cli -e" }
}
if (Have ollama) { Pass "Ollama" } else { Warn "Ollama is not installed" "winget install --id Ollama.Ollama -e (or use the desktop's with -DesktopOllama)" }

Head "3. The repo"
if (-not (Test-Path -LiteralPath (Join-Path $Dir '.git'))) { Fail "$Dir is not a git repository" "run laptop-setup.ps1" }
else {
    $origin = ("" + (Gx remote get-url origin)).Trim()
    if ($origin -match 'r-anthony-graves/ray-code') { Pass "origin is ray-code" } else { Fail "origin is '$origin'" "git -C $Dir remote set-url origin https://github.com/r-anthony-graves/ray-code.git" }
    $branch = ("" + (Gx rev-parse --abbrev-ref HEAD)).Trim()
    if ($branch -eq 'main') { Pass "on branch main" } else { Warn "on branch '$branch': the two-way sync only runs on main" "git -C $Dir checkout main" }
    if (-not $OnDesktop) {
        $push = ("" + (Gx config remote.origin.push)).Trim()
        if ($push -eq 'refs/heads/main:refs/heads/laptop') { Pass "a plain git push goes to the laptop branch" } else { Warn "git push is not pointed at the laptop branch (it is '$push')" "git -C $Dir config remote.origin.push refs/heads/main:refs/heads/laptop" }
    }
    if (-not $NoFetch) { Gx fetch --quiet origin | Out-Null; if ($script:GitCode -ne 0) { Warn "could not reach GitHub (offline?)" } }
    $behind = $(if ($OnDesktop) { '' } else { ("" + (Gx rev-list --count 'HEAD..origin/main')).Trim() })
    if ($behind -match '^\d+$') { if ([int]$behind -eq 0) { Pass "up to date with GitHub's main" } else { Warn "$behind commit(s) behind GitHub's main" "the sync task does this every 15 minutes, or run seven\scripts\laptop-sync.ps1" } }
    $dirty = @(Gx status --porcelain --untracked-files=no | Where-Object { $_ }).Count
    if ($dirty -eq 0) { Pass "no uncommitted changes" } else { Warn "$dirty uncommitted change(s)" "the sync saves them as 'Laptop auto-save' on its next run" }
    foreach ($f in 'seven\scripts\laptop-sync.ps1', 'seven\scripts\apply-look.ps1', 'seven\scripts\laptop-shortcut.ps1', 'seven\scripts\import-keys.ps1', 'seven\config\desktop-look.json', 'seven\config\laptop-keys.enc', 'seven\requirements.lock') {
        if (Test-Path -LiteralPath (Join-Path $Dir $f)) { Pass "$f is in the repo" } else { Fail "$f is missing" "git -C $Dir pull (the desktop must have pushed it)" }
    }
}

Head "4. Seven's Python"
if (-not (Test-Path -LiteralPath $Venv)) { Fail "seven\.venv is not built" "laptop-setup.ps1 (step 4)" }
else {
    Push-Location $Seven          # as Seven starts: from its own folder (another "seven" folder in the home directory would shadow it)
    $o = & $Venv -c "import seven, seven.forex, seven.council; from seven import config; s = config.Settings.from_env(); print('ui=' + s.ui, 'model=' + s.model, 'ollama=' + s.ollama_url)" 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE; Pop-Location
    if ($code -eq 0) { Pass "Seven imports" ($o -join ' ') } else { Fail "Seven does not import: $(($o | Select-Object -Last 2) -join ' | ')" "$Venv -m pip install -r $Seven\requirements.lock" }
}

if (-not $OnDesktop) {
    Head "5. Automatic two-way sync"
    $task = Get-ScheduledTask -TaskName 'Seven laptop sync' -ErrorAction SilentlyContinue
    if (-not $task) { Fail "the scheduled task 'Seven laptop sync' is not registered" "laptop-setup.ps1 (step 8)" }
    else {
        if ($task.State -eq 'Disabled') { Fail "the sync task is disabled" "Enable-ScheduledTask -TaskName 'Seven laptop sync'" } else { Pass "sync task registered ($($task.State))" }
        $info = Get-ScheduledTaskInfo -TaskName 'Seven laptop sync' -ErrorAction SilentlyContinue
        if ($info -and $info.LastRunTime -gt (Get-Date).AddYears(-1)) {
            if ($info.LastRunTime -lt (Get-Date).AddHours(-2)) { Warn "the sync last ran $($info.LastRunTime) (over 2 hours ago)" "is the laptop asleep? run seven\scripts\laptop-sync.ps1 by hand" } else { Pass "sync last ran $($info.LastRunTime)" }
        } else { Warn "the sync task has not run yet" "wait 15 minutes or run seven\scripts\laptop-sync.ps1" }
    }
    $state = Join-Path $HOME '.seven-laptop-sync'
    if (Test-Path (Join-Path $state 'off')) { Warn "the sync is PAUSED (an 'off' file is in $state)" "delete that file to resume" }
    $st = Join-Path $state 'status.txt'
    if (Test-Path $st) { $t = (Get-Content $st -Raw).Trim(); if ($t -match 'STUCK') { Fail "sync status: $t" "read $state\laptop-sync.log; fix the clash by hand in $Dir" } else { Pass "sync status: $t" } } else { Warn "no sync status yet" "run seven\scripts\laptop-sync.ps1 once" }
}

Head "6. The window's look"
$want = $null; $lookFile = Join-Path $Seven 'config\desktop-look.json'
if (Test-Path $lookFile) { try { $want = Get-Content $lookFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { } }
foreach ($n in 'SEVEN_UI', 'SEVEN_SHELL') {
    $have = UserVar $n; $exp = if ($want) { $want.env.$n } else { $null }
    if (-not $have) { Warn "$n is not set (default look)" "seven\scripts\apply-look.ps1" }
    elseif ($exp -and $have -ne $exp) { Warn "$n is '$have' here and '$exp' on the desktop" "apply-look.ps1 -Force, if you want the desktop's" }
    else { Pass "$n = $have" }
}
$stateDir = Join-Path $Seven 'state'
if ($want) {
    foreach ($p in $want.state.PSObject.Properties) {
        $f = Join-Path $stateDir $p.Name
        if (-not (Test-Path $f)) { Warn "state\$($p.Name) is missing (default)" "apply-look.ps1"; continue }
        $same = $false; try { $same = ((Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json | ConvertTo-Json -Depth 6) -eq ($p.Value | ConvertTo-Json -Depth 6)) } catch { }
        if ($same) { Pass "state\$($p.Name) matches the desktop" } else { Warn "state\$($p.Name) differs from the desktop (your own choice?)" "apply-look.ps1 -Force to take the desktop's" }
    }
}
if ((UserVar 'SEVEN_SHELL') -eq 'electron') {
    $el = @((UserVar 'SEVEN_ELECTRON'), (Join-Path $Seven 'window-shell\node_modules\electron\dist\electron.exe'), (Join-Path $Seven 'avatar\node_modules\electron\dist\electron.exe')) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($el) { Pass "Electron is installed" } else { Warn "SEVEN_SHELL is electron but Electron is not installed (the window opens in Edge)" "seven\scripts\apply-look.ps1" }
}

Head "7. Shortcuts"
$shell = New-Object -ComObject WScript.Shell
$folders = @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'), [Environment]::GetFolderPath('Startup')) | Where-Object { $_ -and (Test-Path $_) }
$old = 0; $mine = $null
foreach ($f in $folders) {
    foreach ($l in Get-ChildItem $f -Filter '*.lnk' -File -Recurse -ErrorAction SilentlyContinue) {
        $s = $shell.CreateShortcut($l.FullName)
        if ("$($s.TargetPath) $($s.Arguments) $($s.WorkingDirectory)" -match '(?i)seven-l1|seven_l1|run-seven\.ps1') { $old++; Fail "$($l.FullName) still starts the old Seven-L1" "seven\scripts\laptop-shortcut.ps1" }
        if ($l.Name -eq 'Seven.lnk' -and $s.Arguments -eq '-m seven.window.app') { $mine = $s }
    }
}
if ($old -eq 0) { Pass "no shortcut starts the old Seven-L1" }
if ($mine) { Pass "a 'Seven' shortcut runs the desktop's window command"; if (-not (Test-Path $mine.TargetPath)) { Fail "its target $($mine.TargetPath) is missing" "laptop-setup.ps1 (step 4)" } }
elseif (-not $OnDesktop) { Warn "no 'Seven' shortcut that runs seven.window.app" "seven\scripts\laptop-shortcut.ps1" }
foreach ($t in Get-ScheduledTask -ErrorAction SilentlyContinue) { foreach ($a in $t.Actions) { if ("$($a.Execute) $($a.Arguments)" -match '(?i)seven-l1|seven_l1|run-seven\.ps1') { Warn "scheduled task '$($t.TaskName)' starts Seven-L1" "Disable-ScheduledTask -TaskName '$($t.TaskName)'" } } }

Head "8. Keys (set or not; never shown)"
foreach ($n in 'DEEPSEEK_API_KEY', 'OANDA_PRACTICE_TOKEN', 'OANDA_PRACTICE_ACCOUNT') {
    $v = UserVar $n
    if ($v) { Pass "$n is set ($($v.Length) characters)" } else { Warn "$n is not set" "seven\scripts\import-keys.ps1 (asks for the password)" }
}

Head "9. Ollama and the model"
$ou = $(if (UserVar 'SEVEN_OLLAMA_URL') { (UserVar 'SEVEN_OLLAMA_URL').TrimEnd('/') } else { 'http://127.0.0.1:11434' })
$tags = $null; try { $tags = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "$ou/api/tags").Content | ConvertFrom-Json } catch { }
if (-not $tags) { Fail "no Ollama answers at $ou" "start the Ollama app (or fix SEVEN_OLLAMA_URL)" }
else {
    Pass "Ollama answers at $ou"
    $names = @($tags.models | ForEach-Object { $_.name })
    $model = UserVar 'SEVEN_MODEL'; if (-not $model) { $model = 'seven-qwythos' }
    if ($names | Where-Object { $_ -eq $model -or $_ -eq "${model}:latest" }) { Pass "the model '$model' is there" } else { Fail "the model '$model' is not in Ollama" "ollama create seven-qwythos -f $Seven\ollama\seven-qwythos.Modelfile (or -DesktopOllama for seven-v33)" }
    foreach ($m in 'qwen3-1.7b-cpu', 'nomic-embed-cpu') { if ($names | Where-Object { $_ -like "$m*" }) { Pass "$m (Hindsight's) is there" } else { Warn "$m is missing: Hindsight cannot start" "laptop-setup.ps1 (step 5)" } }
}

Head "10. Hindsight (memory)"
$h = $null; try { $h = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 'http://127.0.0.1:8890/health' } catch { }
if ($h -and $h.Content -match 'healthy') { Pass "Hindsight is healthy on port 8890" }
else { Warn "Hindsight does not answer on 127.0.0.1:8890 (Seven runs with memory off)" "Start-ScheduledTask -TaskName hindsight, or powershell -File $HindsightDir\start_hindsight.ps1" }
if ($h) { try { $b = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 'http://127.0.0.1:8890/v1/default/banks/ray/config'; Pass "the bank 'ray' exists" } catch { Warn "the bank 'ray' is missing" "python $HindsightDir\setup_bank.py" } }

Write-Host ""
$colour = if ($script:fail -gt 0) { 'Red' } elseif ($script:warn -gt 0) { 'Yellow' } else { 'Green' }
Write-Host ("RESULT: {0} passed, {1} warning(s), {2} failed" -f $script:pass, $script:warn, $script:fail) -ForegroundColor $colour
if ($script:fail -gt 0) { exit 1 } else { exit 0 }
