# Handoff: check that Seven is set up properly on the laptop

Written 2026-11-04 by the desktop session. Read this top to bottom, then do "What to do". It is written for a Claude session running on
the LAPTOP (or for Ray doing the same by hand). The desktop session could not see the laptop: everything below was built and tested on
the desktop only, so **none of it has been proven on the laptop yet**. Your job is to find out what works, fix what is safe to fix, and
report the rest.

## What was built (all today, 2026-11-04)

| Piece | File (in `seven/scripts/` unless noted) | What it does |
|---|---|---|
| Setup | `laptop-setup.ps1` | One script, ten steps: tools, GitHub login, clone of `ray-code`, Seven's Python (`seven\.venv`), Ollama models, Hindsight (empty memory), `-DesktopOllama`, automatic sync task, "Seven" shortcut, the desktop's window look. Safe to run again. `-DryRun` says what it would do. |
| Two-way sync, laptop | `laptop-sync.ps1` | Scheduled task **Seven laptop sync** (logon + every 15 min). Saves the laptop's edits as a commit, merges the desktop's snapshot (`origin/main`), pushes `main` to the **`laptop` branch only**. A clash is undone and logged, never forced. |
| Two-way sync, desktop | `laptop-import.ps1` | Desktop task **Seven laptop import** (every 15 min). Turns each new laptop commit into a patch and applies it to the desktop's `D:\Ray-Code` main. A patch that does not apply is kept and logged, never forced. |
| Keys | `export-keys.ps1`, `import-keys.ps1`, `config\laptop-keys.enc` | The DeepSeek key and the two OANDA values, password-encrypted. Ray types the password himself, in his own terminal. |
| Look | `export-look.ps1`, `apply-look.ps1`, `config\desktop-look.json` | Gives the laptop the desktop's window look: `SEVEN_UI=aurora`, `SEVEN_SHELL=electron`, the palette/theme/avatar files, and Electron. |
| Shortcut | `laptop-shortcut.ps1` | "Seven" shortcut that opens the same window as the desktop; repoints any old Seven-L1 shortcut (originals kept as `.seven-l1-backup`, `-Undo` restores). |
| **This check** | `laptop-check.ps1` | Read-only. Prints PASS / WARN / FAIL for every piece above, with a `fix:` command on each problem. |
| Notes | `seven-docs\ui-design-notes.md` (and `.html`) | What the window's look is made of. |

Where things live:
- **`r-anthony-graves/ray-code`** (GitHub, **private**): the whole Seven repo. The laptop clones it (to `D:\Ray-Code` if the laptop has a D:
  drive, otherwise `~\Ray-Code`). GitHub `main` is a chain of "Sync from D:\Ray-Code main <sha>" snapshot commits made by the desktop's
  `sync-to-github.ps1` (nightly 00:00 PT, or when Ray says "push"). It is **not** the desktop's own git history.
- **`r-anthony-graves/SevensLaptop`** (GitHub, **public**): a separate repo, the laptop's own working repo. It holds a copy of `laptop-setup.ps1`
  and `docs/`. **Nothing secret may ever go in it.** The old laptop app, Seven-L1, used to live there and was removed today.
- Why the laptop looked different from the desktop: the desktop's look is two Windows user variables plus three files in `seven\state\`,
  none of which are in git. `apply-look.ps1` carries them over.

## Rules (do not break these)

1. **Never print, log, paste or ask for a key, token or password.** The check shows only whether a key is set and how long it is. If the
   keys need importing, tell Ray to run `import-keys.ps1` **himself, in his own PowerShell window**, and type the password there.
2. **Never push to GitHub `main`.** Only the desktop writes `main`. The laptop writes the `laptop` branch (the sync does it). No
   `git push --force`, no `git reset --hard` on the clone without Ray saying so.
3. **Do not put anything secret, or anything from `seven\state\`, `.env` files, `pgdata`, `.venv`, model files, in a commit.** The sync already
   holds back names that look like secrets and files over 25 MB; do not work around that.
4. Do not use `-Force` (`apply-look.ps1 -Force`, etc.) without asking Ray: it replaces choices he made on the laptop.
5. Do not edit, delete or disable anything on the **desktop**. If the desktop needs something, say so in the report.
6. Do not delete the `.seven-l1-backup` shortcut backups or the old Seven-L1 files. Repoint, do not remove.
7. Ask before anything that downloads gigabytes (the 6.5 GB model, Electron) unless Ray has already said to go ahead.

## What to do

### Step 1: find the repo and run the check

The repo is `D:\Ray-Code` or `~\Ray-Code`. If neither exists, setup was never run: stop here and tell Ray (the script to run is `laptop-setup.ps1`
from the SevensLaptop repo; run it with `-DryRun` first and show him the output).

```powershell
cd <the repo>
powershell -NoProfile -ExecutionPolicy Bypass -File seven\scripts\laptop-check.ps1
```

If `laptop-check.ps1` is not there yet, the clone is behind: run `powershell -File seven\scripts\laptop-sync.ps1` (or `git pull --ff-only`),
or take `laptop-check.ps1` from the SevensLaptop repo's root.

Read the last line: `RESULT: N passed, N warning(s), N failed`. Exit code 1 means at least one FAIL.

### Step 2: deal with each FAIL and WARN

Every line has its own `fix:`. The usual ones:

| Line says | Likely cause | What to do |
|---|---|---|
| `seven\scripts\... is missing` | The clone is older than the desktop's last push. | Run `seven\scripts\laptop-sync.ps1`, then check again. If still missing, the desktop has not pushed: tell Ray to say "push" on the desktop. |
| `origin is '...'` not ray-code | Cloned from somewhere else. | Show Ray; do not change the remote without his OK. |
| `scheduled task 'Seven laptop sync' is not registered` | Setup step 8 did not run (the script was missing at the time). | Run `laptop-setup.ps1` again. It registers the task. |
| `sync status: STUCK ...` | A merge clash, or a failed push. Nothing was overwritten. | Read `~\.seven-laptop-sync\laptop-sync.log`. Show Ray the clash; fix by hand in the repo only with his OK. |
| `the sync is PAUSED` | An empty file named `off` in `~\.seven-laptop-sync\`. | Ask Ray whether he paused it on purpose. |
| `... still starts the old Seven-L1` | Old shortcut. | `seven\scripts\laptop-shortcut.ps1` (it keeps a backup; `-Undo` reverses). |
| `SEVEN_UI` / `SEVEN_SHELL` not set, state files missing | Look not applied. | `seven\scripts\apply-look.ps1` (add `-NoElectron` to skip the big download). Restart Seven afterwards. |
| `Electron is not installed` | `apply-look.ps1` was skipped or failed. | Run it again. Needs Node.js (it installs it with winget). The window works without Electron: it opens in Edge. |
| `DEEPSEEK_API_KEY` / `OANDA_...` not set | Keys not imported. | Ray runs `seven\scripts\import-keys.ps1 -Check` himself (it asks for the password and sets nothing), then without `-Check`. Then a new PowerShell window and a Seven restart. |
| `the model 'seven-qwythos' is not in Ollama` | Model not built, or Ollama not running. | Start the Ollama app. Building the model downloads about 6.5 GB: ask first. |
| `no Ollama answers` | Ollama is not running. | Start it. If Ray set `SEVEN_OLLAMA_URL` to the desktop, the desktop's Ollama must listen on the network (`OLLAMA_HOST=0.0.0.0`) with port 11434 allowed in its firewall. |
| `Hindsight does not answer` | Not started. Seven still runs, with memory off. | `Start-ScheduledTask -TaskName hindsight` or `powershell -File ~\hindsight\start_hindsight.ps1`. If it never installed, run `laptop-setup.ps1`. |

After each fix, run the check again. Stop when the only lines left are ones you cannot or should not change.

### Step 3: the things the check cannot see (do these with Ray)

1. **Look at the window.** Start "Seven" from the Desktop or Start menu. It should open in an Electron window in the aurora look with the
   graphite palette (muted slate), dark theme, and the orb in the strip under the title bar. The Seven-L1 window must not appear. If the
   look is wrong, say what you see: the design notes (`seven\seven-docs\ui-design-notes.md`) list what controls each part.
2. **Keys, without showing them.** Ray runs `import-keys.ps1 -Check` in his own terminal. A wrong password prints "wrong password, or the
   file was changed" and sets nothing.
3. **One round trip of the two-way sync (optional, ask Ray first).** On the laptop create a harmless text file in the repo, for example
   `seven\seven-docs\laptop-sync-test.txt` containing one line. Run `laptop-sync.ps1`. The file should be pushed to the `laptop` branch.
   On the desktop the import task applies it within 15 minutes (`D:\Ray-Code\seven\logs\laptop-import.log` says so). Then delete the file
   on the laptop and sync again so the desktop's copy goes away too. Report whether it arrived. Do not do this step if Ray objects:
   it puts a commit on his desktop `main`.
4. **A desktop-to-laptop trip.** After the desktop's next "push" (or the 00:00 PT sync), `laptop-check.ps1` should show the laptop no more
   than a few commits behind, and the laptop's auto-save commits should not have vanished.

### Step 4: report

Reply to Ray with:
- the `RESULT:` line before and after your fixes;
- every FAIL or WARN that is left, one line each, with what is needed and who has to do it (Ray, the desktop, or you);
- what you changed (commands you ran, files you touched), so he can undo it;
- the answers to step 3, in plain words (what the window looked like, whether the round trip worked);
- anything surprising.

Do not paste keys, passwords or the contents of `laptop-keys.enc`.

## Known weak spots (look here first when something is off)

- **Never run on the laptop**: the winget installs, the GitHub browser login, the Ollama model download, the Electron install on a laptop,
  the first real laptop sync, the registration of the scheduled task on the laptop, `import-keys.ps1` with the real file. The desktop tests
  used pretend machines and temp folders.
- **Seven's settings default to `D:\Ray-Code\...` paths** (office, board, council, web folders). A laptop without a D: drive needs matching
  `SEVEN_*` variables (see `seven\seven\config.py`) or the features that use them will fail. `laptop-setup.ps1` prints a note about this.
- **The model differs**: the desktop runs `seven-v33`, a trained model that exists only as a file on the desktop. The laptop gets
  `seven-qwythos` (the default) unless set up with `-DesktopOllama http://<desktop>:11434`. Answers will differ.
- **Hindsight starts empty** on the laptop. Ray's desktop memories were deliberately not copied.
- **The scheduled tasks run PowerShell hidden**; a console window may flash briefly every 15 minutes on some Windows setups.
- **Laptop merge-conflict resolutions are not carried to the desktop** (the import skips merge commits). Only the laptop's own edits are.
- **Auto-merge**: the desktop applies laptop commits to `main` with no review (Ray chose this). Pause it with an empty file
  `D:\Ray-Code\.git\laptop-import.off` on the desktop, or `~\.seven-laptop-sync\off` on the laptop.
- GitHub `main` only moves when the desktop pushes. If the laptop looks stale, check the desktop's last push first.

## Undo, in order of how much they undo

| To undo | Command |
|---|---|
| Stop the sync for now | create an empty file `~\.seven-laptop-sync\off` (delete it to resume) |
| Remove the sync task | `Unregister-ScheduledTask -TaskName 'Seven laptop sync' -Confirm:$false` |
| Put the old shortcuts back | `seven\scripts\laptop-shortcut.ps1 -Undo` |
| Go back to the default look | delete the user variables `SEVEN_UI` and `SEVEN_SHELL` and the three files in `seven\state\` named in `config\desktop-look.json` |
| Stop Hindsight | `Stop-ScheduledTask -TaskName hindsight`, then end `hindsight-api.exe` and the `postgres.exe` processes under `~\hindsight` in Task Manager (the laptop setup writes no stop script; `~\hindsight\pgdata\` is its database) |

## Where to read more

`seven\scripts\laptop-setup.ps1` (the header lists every step and switch), `laptop-sync.ps1` and `laptop-import.ps1` (the headers explain the
rules), `seven\seven-docs\ui-design-notes.md`, and the self-tests that prove the desktop-side logic: `laptop-sync-selftest.ps1`,
`keys-selftest.ps1`, `laptop-shortcut-selftest.ps1`, `look-selftest.ps1` (each builds temp folders and touches nothing real).
