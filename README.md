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
