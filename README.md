# SevensLaptop

Working repository for this laptop (`OlokunAje`).

**This repository is public.** Nothing secret belongs in it: no API keys, no
certificates, no database files, no exports of Ade's memory. It sits on `F:\`
beside all of those, so the `.gitignore` refuses the obvious shapes by name
rather than trusting a reviewer to notice them.

## Where it sits

`F:\SevensLaptop` is inside the `F:\` work tree, which is a separate git
repository rooted at the drive itself. This one is nested, so files here
belong to this repository and not to that one.

## Setting up Seven on this laptop

`laptop-setup.ps1` sets up Seven here. It clones the private `ray-code` repo (read-only, push turned off), builds Seven's
Python environment, builds the Ollama models, and installs Hindsight with an empty memory. Run it in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File laptop-setup.ps1 -DryRun    # say what it would do
powershell -NoProfile -ExecutionPolicy Bypass -File laptop-setup.ps1             # do it
powershell -NoProfile -ExecutionPolicy Bypass -File laptop-setup.ps1 -DesktopOllama http://DESKTOP:11434   # use the desktop's seven-v33
```

It can be run again: it only does what is not done yet. The first lines of the script list every option. It installs
Git, Python 3.12, the GitHub CLI and Ollama with winget when they are missing, and opens a browser window to log in to GitHub.

### Automatic updates both ways

The script also registers a scheduled task, "Seven laptop sync" (at logon and every 15 minutes), that runs `seven\scripts\laptop-sync.ps1`
from the cloned repo. It saves this laptop's edits as commits (never anything that looks like a secret), merges the desktop's latest
snapshot, and pushes to the `laptop` branch of the private `ray-code` repo, never to its `main`. On the desktop a matching task
applies those commits to the desktop's `main`. A clash is logged and left for a person, never forced. Log and status are in
`~\.seven-laptop-sync\`; an empty file named `off` there pauses it. `-NoAutoSync` skips the task.

### The Seven window and its look

The script also makes a "Seven" shortcut that opens the same window as the desktop (and repoints any old Seven-L1 shortcut), then copies
the desktop's window look: the aurora look, the saved palette, theme and avatar settings, and Electron. `-NoShortcut`, `-NoLook` and
`-NoElectron` skip those parts. Design notes for the window are in `docs/ui-design-notes.md`.

### Checking the setup

`laptop-check.ps1` only reads. It prints PASS, WARN or FAIL for the tools, the repo, Seven's Python, the sync task, the window look,
the shortcuts, the keys (set or not, never shown), Ollama and Hindsight, with a "fix:" command on each problem:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File laptop-check.ps1
```

`docs/HANDOFF-laptop-setup-check.md` is the hand-off for a session on the laptop: what was built, the rules, the steps, what to report.
