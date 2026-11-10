# Sets up the laptop for Seven's ROUTER tools (router_status, router_clients, router_forwards). Ray, 2026-11-09: "add what i need to
# the laptop repo to set up network, the sync does not seem to do it". The sync only moves files; it cannot install a Python package,
# write box-specific settings or touch Tailscale. This script does those parts, on the laptop, and pulls NOTHING from the desktop.
# It holds no address, fingerprint, name or password of anyone's: you pass them on the command line.
# Run it again any time: every step is skipped when it is already done, nothing is removed, nothing is overwritten.
# laptop-update.ps1 runs it as its last step; it can also be run alone, from the laptop's Seven checkout or from this repo's folder.
#
#   A. The router library: the 9 pinned packages (asusrouter and what it needs) from the public Python package index, into
#      <Dir>\seven\.venv. Only the ones that are missing or at another version.
#   B. <Dir>\seven\config\router.json {host, port, cert_sha256}, ONLY when it does not exist yet and -RouterPin is given.
#      An existing file is never changed (a different pin is reported, not written).
#   C. Tailscale: -AcceptRoutes runs `tailscale set --accept-routes=true` (so the laptop reaches the router through the subnet route
#      your home PC advertises). Without the switch it only reports the setting.
#   D. A plain TCP connect to <RouterHost>:8443 (3 seconds, nothing sent, no sign-in) to say whether the router answers.
#   E. What is left for you: approving the route, storing the router login (typed by you, never by this script), a Restart.
#
#   laptop-network.ps1 -RouterPin <64 hex characters> -AcceptRoutes        everything (the pin is the router's certificate fingerprint)
#   laptop-network.ps1                                                     only the library, and a report of the rest
#   laptop-network.ps1 -RouterHost 192.168.1.1 -RouterPin <pin>            another router address (a private address only)
#   laptop-network.ps1 -Dir F:\Ray-Code                                    another Seven checkout (default: the checkout this file is in, else F:\Ray-Code)
#   laptop-network.ps1 -DryRun                                             say what would be done; nothing is installed, written or changed
#   laptop-network.ps1 -NoConnect                                          skip the connect test
param(
    [string]$Dir = '',
    [string]$RouterHost = '192.168.50.1',
    [int]$RouterPort = 0,
    [string]$RouterPin = '',
    [int]$AdminPort = 8443,
    [string]$ProbeHost = '',
    [switch]$AcceptRoutes,
    [switch]$NoConnect,
    [switch]$DryRun,
    [string]$Python = '',
    [string]$Tailscale = ''
)

$ErrorActionPreference = 'Stop'
$Notes = New-Object System.Collections.Generic.List[string]
$Pins = @('aiohappyeyeballs==2.7.1', 'aiohttp==3.14.5', 'aiosignal==1.4.0', 'asusrouter==1.21.3', 'frozenlist==1.8.0',
          'multidict==7.2.1', 'propcache==0.5.4', 'xmltodict==1.0.4', 'yarl==1.25.1')      # seven\requirements.lock, 2026-11-06

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Say($text) { Write-Host "  $text" }
function Warn($text) { Write-Host "  NOTE: $text" -ForegroundColor Yellow; $Notes.Add($text) }
function Fail($text) { Write-Host "STOPPED: $text" -ForegroundColor Red; exit 1 }

if (-not $Dir) {
    $up = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    if ($up -and (Test-Path -LiteralPath (Join-Path $up 'seven\requirements.lock'))) { $Dir = $up } else { $Dir = 'F:\Ray-Code' }
}
$Seven = Join-Path $Dir 'seven'
$RouterFile = Join-Path $Seven 'config\router.json'
if (-not $ProbeHost) { $ProbeHost = $RouterHost }

function Test-PrivateV4([string]$h) {
    $ip = $null
    if (-not [System.Net.IPAddress]::TryParse($h, [ref]$ip)) { return $false }
    if ($ip.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    $b = $ip.GetAddressBytes()
    return ($b[0] -eq 10) -or ($b[0] -eq 192 -and $b[1] -eq 168) -or ($b[0] -eq 172 -and $b[1] -ge 16 -and $b[1] -le 31)
}

# ================= the checkout
Step "Seven checkout: $Dir"
if (-not (Test-Path -LiteralPath (Join-Path $Seven 'requirements.lock'))) { Fail "no Seven checkout at $Dir (pass -Dir, or run laptop-setup.ps1 first)" }
$routerCode = Join-Path $Seven 'seven\servers\router.py'
if (Test-Path -LiteralPath $routerCode) { Say "the router tools are in this checkout" }
else { Warn "this checkout has no router tools yet (seven\seven\servers\router.py is missing): it has not merged GitHub's main. Run seven\scripts\laptop-unjam.ps1 (or wait for the 15-minute sync), then run this again." }
if (-not (Test-Path -LiteralPath (Join-Path $Seven 'scripts\store-router-login.ps1'))) { Warn "seven\scripts\store-router-login.ps1 is missing here too (same cause)" }

# ================= A. the library
Step "A. Router library (asusrouter and 8 packages it needs)"
if (-not $Python) { $Python = Join-Path $Seven '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { Fail "no Python at $Python (run laptop-setup.ps1 to make Seven's venv, or pass -Python)" }
$missing = New-Object System.Collections.Generic.List[string]
foreach ($pin in $Pins) {
    $name, $want = $pin -split '=='
    $have = ''
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $out = & $Python -m pip show $name 2>&1 | ForEach-Object { "$_" }; $code = $LASTEXITCODE } finally { $ErrorActionPreference = $old }
    if ($code -eq 0) { foreach ($line in $out) { if ($line -match '^Version:\s*(\S+)') { $have = $Matches[1] } } }
    if ($have -eq $want) { Say "$pin is installed" } else { Say "${pin}: $(if ($have) { "found $have" } else { 'not installed' })"; $missing.Add($pin) }
}
if ($missing.Count -eq 0) { Say "nothing to install" }
elseif ($DryRun) { Say "[dry run] pip install $($missing -join ' ')" }
else {
    Say "installing $($missing.Count) package(s) from the Python package index"
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & $Python -m pip install @($missing) 2>&1 | ForEach-Object { Write-Host "    $_" }; $code = $LASTEXITCODE } finally { $ErrorActionPreference = $old }
    if ($code -ne 0) { Fail "pip install failed (exit code $code): read what it printed above" }
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & $Python -c "import asusrouter" 2>&1 | Out-Null; $code = $LASTEXITCODE } finally { $ErrorActionPreference = $old }
    if ($code -ne 0) { Fail "asusrouter was installed but does not import" }
    Say "asusrouter imports"
}

# ================= B. router.json
Step "B. config\router.json"
$pinOk = $RouterPin -match '^[0-9a-fA-F]{64}$'
if (Test-Path -LiteralPath $RouterFile) {
    $cur = $null
    try { $cur = Get-Content -LiteralPath $RouterFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { }
    if ($cur -and $cur.host -and ("$($cur.cert_sha256)" -match '^[0-9a-fA-F]{64}$')) {
        Say "exists: host $($cur.host), port $($cur.port), pin set (not changed)"
        if ($pinOk -and "$($cur.cert_sha256)".ToLower() -ne $RouterPin.ToLower()) { Warn "the existing router.json has a different pin than -RouterPin; it was NOT changed (edit it yourself if the router's certificate changed)" }
    } else { Warn "router.json exists but is incomplete (it needs host, port and a 64-hex cert_sha256); it was NOT changed" }
}
elseif (-not $RouterPin) { Warn "router.json does not exist. Run again with -RouterPin <the router's certificate fingerprint, 64 hex characters>" }
elseif (-not $pinOk) { Fail "-RouterPin must be 64 hexadecimal characters" }
elseif (-not (Test-PrivateV4 $RouterHost)) { Fail "-RouterHost must be a private IPv4 address (10.x, 172.16-31.x or 192.168.x)" }
elseif ($DryRun) { Say "[dry run] write $RouterFile (host $RouterHost, port $RouterPort)" }
else {
    New-Item -ItemType Directory -Path (Split-Path -Parent $RouterFile) -Force | Out-Null
    $json = '{"host": "' + $RouterHost + '", "port": ' + $RouterPort + ', "cert_sha256": "' + $RouterPin.ToLower() + '"}'
    [System.IO.File]::WriteAllText($RouterFile, $json + "`n", (New-Object System.Text.UTF8Encoding($false)))
    Say "wrote $RouterFile (host $RouterHost, port $RouterPort)"
}

# ================= C. Tailscale
Step "C. Tailscale: use the subnet route"
if (-not $Tailscale) {
    $cmd = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($cmd) { $Tailscale = $cmd.Source } elseif (Test-Path -LiteralPath 'C:\Program Files\Tailscale\tailscale.exe') { $Tailscale = 'C:\Program Files\Tailscale\tailscale.exe' }
}
if (-not $Tailscale -or -not (Test-Path -LiteralPath $Tailscale)) { Warn "Tailscale is not installed here: at home the router is reached directly, away from home it needs Tailscale and the route" }
else {
    $routeAll = $null
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $prefs = (& $Tailscale debug prefs 2>$null | Out-String) | ConvertFrom-Json; if ($prefs) { $routeAll = $prefs.RouteAll } } catch { } finally { $ErrorActionPreference = $old }
    if ($routeAll -eq $true) { Say "accept-routes is already ON" }
    elseif ($AcceptRoutes) {
        if ($DryRun) { Say "[dry run] tailscale set --accept-routes=true" }
        else {
            $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
            try { & $Tailscale set --accept-routes=true 2>&1 | ForEach-Object { Write-Host "    $_" }; $code = $LASTEXITCODE } finally { $ErrorActionPreference = $old }
            if ($code -ne 0) { Warn "tailscale set --accept-routes=true failed (exit code $code); run it yourself in an administrator window" } else { Say "accept-routes is now ON" }
        }
    }
    else { Say "accept-routes is $(if ($routeAll -eq $false) { 'OFF' } else { 'unknown' }); add -AcceptRoutes to turn it on (or: tailscale set --accept-routes=true)" }
}

# ================= D. does the router answer?
Step "D. Does the router answer on ${ProbeHost}:$AdminPort? (a plain connect, nothing sent)"
if ($NoConnect -or $DryRun) { Say "skipped" }
else {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $ar = $client.BeginConnect($ProbeHost, $AdminPort, $null, $null)
        if ($ar.AsyncWaitHandle.WaitOne(3000) -and $client.Connected) { Say "yes, it answers" }
        else { Warn "no answer in 3 seconds. At home that means the address is wrong or the router is off; away from home it means the Tailscale route is not working yet." }
    } catch { Warn "no answer ($($_.Exception.Message))" }
    finally { $client.Close() }
}

# ================= E. what is left
Step "What is left (yours to do)"
Say "1. The route: in the Tailscale admin console the home PC's route to the router must be approved, and that PC must be on."
Say "2. The router login, typed by you into Windows Credential Manager (this script never sees it):"
Say "     powershell -NoProfile -ExecutionPolicy Bypass -File $(Join-Path $Seven 'scripts\store-router-login.ps1')"
Say "3. Check:   powershell -NoProfile -ExecutionPolicy Bypass -File $(Join-Path $Seven 'scripts\laptop-check.ps1')"
Say "4. Restart Seven, then run: $(Join-Path $Seven 'scripts\router-check.ps1')   (or ask Seven to check the router)"
if ($Notes.Count -gt 0) {
    Write-Host ""; Write-Host "Notes:" -ForegroundColor Yellow
    $Notes | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
}
exit 0
