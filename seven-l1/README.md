# Seven-L1

One native desktop app for everything Seven does: PySide6, **no browser
engine** (Ray, 2026-09-17). Say **"Seven"** to wake it.

Seven-L1 is the renamed continuation of **Ade Desktop** (`ade-desktop-laptop`,
2026-11-04). The runtime it talks to is still **Ade OS** on `:8300` — that was
deliberately not renamed, so anything below that says "Ade OS" means the
backend service, not this app.

## What this fork builds

The laptop builds three sections. Upstream Ade Desktop also had Trader, Path
and Code; Ray does not use those here, so they were deleted outright rather
than hidden behind a switch — Trader imported `D:\tradinglocal`'s widgets into
this process and Path read a server that is not on this machine, so both only
ever rendered placeholders.

| Section | State |
|---|---|
| **PM** | built |
| **QA** | built |
| **Lotto** (PythonLotto's odds and simulator, drawn natively) | built |
| **Seven conversation** (the right-hand panel) | built |
| **Orb + voice** | built |

Design history: `docs/superpowers/specs/2026-09-17-ade-desktop-piece-1-design.md`
in ade-ai (those filenames keep the old name; they are real files there).

## Set up once

    py -V:Astral/CPython3.14.0 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

`requirements.txt` pins **PySide6-Essentials 6.11.1**. Essentials leaves out
PySide6-Addons, which is where QtWebEngine lives;
`tests/test_packaging.py` fails if a browser engine ever gets installed.
The `pythonlotto` pin resolves from a **private** GitHub repo, so a fresh
machine needs GitHub auth before that line installs.

## Run

    .\run-seven.ps1            # start, or bring the running one forward
    .\run-seven.ps1 -Status
    .\run-seven.ps1 -Stop

Close hides it to the tray, and the tray's **Quit** ends it. Only one runs
per user: a second launch brings the first forward. A lock file in the state
directory decides which one that is. `-Stop` is a hard kill and leaves the
lock behind, but the lock only counts while its owner is alive, so the next
launch takes it over.

## What it shows

- **Header:** the Ade OS pill, from `/v1/health` every 5 s:
  **UP**, **DOWN** (unreachable, or an error envelope), **BLOCKED**
  (`may_execute_tools: false`; Ade OS answers that with a 503 *and* a body),
  **DEGRADED** (a subsystem is down but tools may run), or **UNKNOWN** (the
  payload can't say). Hover over it for the reason. The brain name comes
  from `/v1/settings` → `resolved.brain` every 30 s.

## The Seven panel

The panel sits on the right of every section. Toggle it with **Seven ◂** in the
header or **Ctrl+Shift+A**, which works in this window only and is never a
system-wide key. It talks to the **main Ade OS on `:8300`** (Ray,
2026-09-18), not the avatar's twin.

| You type (Chat tab) | Goes to |
|---|---|
| a question | `/v1/ask` with the last 40 turns; the answer lands here |
| a bare command line (`git status`, `get-process`) | runs in the shell and streams here; **Stop** kills it |
| `?question` | plain chat, no files read |
| `/coding fix it` (any task type) | an agent does it through the permission gate |
| `!command`, or anything on the **Shell** tab | the shell. **NOT gated by Permission.check()**, as labelled |

- **One turn at a time.** Pressing Enter mid-turn puts your line back in the
  box. A failed call puts your *exact* line back, so Enter retries.
- **Approvals** appear as cards. The window raises itself, and so does the
  tray if the window was hidden. **Only a click** answers a card: Enter and
  shortcuts can't. A card answered in the WebUI reads "Answered elsewhere",
  and a network blip never marks one decided.
- **Commands:** `/help` lists them, from the one table. Also `/clear`,
  `/compact`, `/restore`, `/reset` (pending approvals stay), `/health`,
  `/search`, `/research`, `/skill`, `/unskill`, `/superpowers` (which
  prefers the localised `ade-` skills — Ade OS's own skill names, unchanged),
  and `/upload`, or drop files on the panel.
- **Threads** live in `threads.json` beside `window.json`, separate from the
  avatar's.

## Voice

The wake word is **"Seven"**. `seven_l1/voice/wake.py` also accepts "Sevens"
and an optional "L1" tail (`Seven L1`, `Seven el one`), so saying the full
product name does not swallow the command. A separator and more text are
required, so "Sevenfold" never wakes it.

**The wake variants are reasoned, not measured.** The Ade rule they replaced
was measured against the live recogniser (by the avatar, 2026-08-27); nobody
has yet checked what whisper returns for a spoken "Seven" on this microphone.
`adeos/avatar` still wakes on "Ade" — the two faces no longer share a wake
word.

## Settings (environment)

| Variable | Default | |
|---|---|---|
| `SEVEN_L1_ADE_URL` | `http://127.0.0.1:8300` | which Ade OS the header watches (the avatar's twin is `:8301`) |
| `SEVEN_L1_STATE_DIR` | `%APPDATA%\seven-l1` | `window.json`, `threads-*.json` and `desktop.log` |

Renamed from `ADE_DESKTOP_*` on 2026-11-04. The old names are **not** read as
a fallback, so anything outside this repo that sets them must be updated.
`SEVEN_L1_TRADER_ROOT` is gone: nothing reads it since the Trader section was
removed. `COMMAND_CENTER_DESK` is likewise vestigial here — `tests/test_smoke.py`
still points it at a closed port defensively.

## Test

    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m seven_l1 --smoke --smoke-out=smoke.png

`--smoke` builds the real window headless, polls for 4 s, prints what it
saw as JSON and writes a PNG. It passes with everything DOWN, because DOWN
is a correctly rendered state.

One test is skipped on this machine: `tests/test_pm_logic.py` compares this
app's model against `adeos/records/pmi.py` through a hardcoded
`C:\Users\ray_g\ade-ai` path, and this checkout is under `C:\Users\r_ant`.
`tests/test_qa.py` reads the web's `qaNav.ts` the same way. Both skip rather
than fail, which means they are currently proving nothing.

**If you ever hit a native crash in the tests** (`Windows fatal exception:
access violation`): check whether a widget a test drops has become a
reference cycle. PySide can crash when the garbage collector tears a window
down while a poller thread is delivering a signal. On 2026-09-17 that took
down tradinglocal's suite 6 times out of 6, until the cycle was broken so
dropped windows are freed at their last reference.

## What it runs

Nothing of its own — it starts no processes at all. Every Seven action goes
through Ade OS and its permission gate.
