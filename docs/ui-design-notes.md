# Seven window: UI design notes

Written 2026-11-04 from the page code in `seven/seven/window/page/` (index.html, style.css, glass.css, aurora.css, desk.css,
layout.js, app.js, forex.js, aurora.js) and the desktop's saved settings. It describes the window as it is built. It does not describe
how the window looks on screen: nobody has screenshot-checked it for this document, and several recent pages are marked "unseen"
in the project notes. Where a fact comes from a file, the file is named.

## 1. Why the laptop's window can look different from the desktop's

The window is ONE web page (`index.html` plus scripts) served by Seven's Python hub on a local port and shown in a shell window.
Its whole look is chosen by settings, and the desktop's choices are NOT in the repository:

| Setting | Desktop value | Where it lives | Default if unset |
|---|---|---|---|
| `SEVEN_UI` | `aurora` | Windows user environment variable | `classic` (`config.py`) |
| `SEVEN_SHELL` | `electron` | Windows user environment variable | Edge app window |
| palette | `graphite` | `seven/state/ui_palette.json` (not tracked by git) | none |
| theme | `dark` | `seven/state/ui_theme.json` (not tracked) | follows the system |
| hero avatar | strip on, large, voice-reactive, hue 251, line `glow` | `seven/state/avatar-settings.json` (not tracked) | defaults |

Only `state/model_mode.json` is tracked. So a laptop that has the right code but none of these settings opens in the **classic**
look, in Edge. To match the desktop: set `SEVEN_UI=aurora` (and `SEVEN_SHELL=electron` with Electron installed: `node_modules`
is not in git, so run `npm install` in `seven/window-shell`, or set `SEVEN_ELECTRON` to the program), and copy the three state files.
`seven/scripts/apply-look.ps1` (step 10 of `laptop-setup.ps1`) now does all of this from `seven/config/desktop-look.json`, which
`seven/scripts/export-look.ps1` writes on the desktop. The old laptop app, Seven-L1, was a different program and is no longer in SevensLaptop.

## 2. Three looks, one structure

`server.py` writes the look into the `<html>` tag: `data-ui="classic"`, `data-ui="glass"` or `data-ui="glass" data-look="aurora"`.
Everything else is CSS on those attributes.

- **classic** (`style.css`): plain panels, system colours, light/dark by the system. The default.
- **glass** (`glass.css`): the "slick" look. Warm paper tones, rounded controls, a draggable chat list, resizable table columns, the
  rail that widens when the "7" tile is clicked. Palettes only exist in this look.
- **aurora** (`aurora.css`): glass in blue, plus the hero avatar, the Command Center home and the hero strip on every page.
  The blue tokens apply only when no palette is chosen (`:not([data-palette])`), so a chosen palette replaces the blue.

The desktop is aurora with the **graphite** palette chosen, so it uses graphite's colours inside aurora's structure.

## 3. Layout

```
+------+-------------+---------------------------------------+-----------+
| rail | chats list  | stage                                 | inspector |
| #rail| #chats-col  | header: title, status, view buttons   | (drawer)  |
|      | (draggable  | hero strip (aurora): orb + words      |           |
|      |  grip)      | page content                          |           |
|      |             | say row: input, Send, Stop            |           |
+------+-------------+---------------------------------------+-----------+
```

- **Rail** (`#rail`): "SEVEN" logo tile that widens/narrows it (shows key names when wide); round logo, 34 px, in aurora. Buttons
  radius 12, hover `--soft-fill`, current page `--accent` fill with `--accent-glow`.
- **Header views** (`#views`): Chat, Forex, Notebook, Lab, REA, API, Settings. Settings has sections: Settings, Memory, Plugins,
  Companion, Prompts. Also Chats, Inspector, Light/Dark and Restart buttons.
- **Guide view**: a numbered F-key bar (1 Chat ... 7 Settings) over a scrolling body; this is the "desk" style, see section 7.
- **Command Center** (aurora home): a grid with the hero card on the left; areas `hero quick / hero health / mission chats /
  positions positions`; gap 16 px, cards radius 20 px.
- **Sizes kept in the page only**: chat list min 180 px and at most 40 % of the window; table columns min 40 px; the stage always keeps
  648 px (640 + 8 margin: a 320 px inspector and a 320 px chat). Reloading returns to the default layout.

## 4. Colour

All colour is CSS custom properties. Semantic names are the same in every look: `--ink` (text), `--paper` (page), `--panel`,
`--rail`, `--line`, `--soft` (secondary text), `--soft-fill` / `--hover` (fills), `--accent` / `--on-accent`, `--good`, `--bad`,
`--warn` / `--warn-ink` / `--warn-line`, `--shadow`.

**classic**: light `ink #1b1b1f, paper #fbfbfd, panel #f0f1f5, line #d3d6de, soft #5f6470, you #dfe8ff, warn #ffe8c2, bad #b3261e,
good #1f6f43`. Dark `ink #e7e8ec, paper #17181c, panel #202228, line #3a3d47, soft #a2a7b3, you #2a3558, bad #ff8a80, good #7fd6a4`.

**glass (warm)**: light `ink #2a2620, paper #f6f3ec, panel #fbf9f4, line #e4ddcd, soft #6b6454, accent #2f5d50, good #2f6b4a,
bad #a93a45`. Desk dark `bg #1c1913, panel #221f17, fg #ece6d8, amber #e3b45a, gain #8fc4ae, loss #e08a8f`.

**aurora (blue, no palette chosen)**: dark `ink #c9dee0, paper #000c1c, panel #04203e, line #1f4263, soft #86a6bc, accent #0a8ef0,
good #66d7a8, bad #ff8791, warn-ink #e6b04a`, page background `linear-gradient(160deg, #001020, #001e36 58%, #031a2e)`, glass fill
`rgba(4,32,62,.66)` with a `rgba(120,190,255,.20)` edge. Light `ink #0e2740, paper #e6f5ff, panel #eef8ff, accent #0784e3`.

**The eight muted palettes** (glass.css; Ray asked for these because he dislikes pastel and neon). All set `color-scheme: light`,
share `bad #a2392f, good #3d6b46, warn-ink #6a5320` and a `0 6px 24px` shadow at 16 % of the ink colour:

| Palette | paper | panel | ink | accent |
|---|---|---|---|---|
| graphite (desktop's) | #e8ebef | #f5f6f8 | #1b2430 | #3f5b7a |
| charcoal | #e6e6e6 | #f4f4f4 | #16181c | #2b2f36 |
| ink | #e4e6ed | #f3f4f7 | #1a1d2e | #3b4468 |
| stone | #eae6e0 | #f6f4f1 | #2a2622 | #8c5a44 |
| plum | #e9e4e8 | #f5f3f5 | #2a1e27 | #5c4256 |
| pine | #e3e9e6 | #f2f5f4 | #17261f | #2f5f58 |
| oxblood | #ebe4e2 | #f6f3f2 | #2b1b1a | #7d3f3a |
| olive | #e9e8df | #f5f5f1 | #24261a | #5f6336 |

Rule: gain is green and loss is red in every look and palette. Warnings are amber/brown.

## 5. Type

- Body: `"Segoe UI", system-ui, sans-serif`, 15 px (glass and aurora).
- **Seven's replies** are set in serif: `Georgia, "Iowan Old Style", serif`, 17 px, line height 1.7, with no bubble. Ray's own messages
  are a filled accent bubble (radius 18 px with a 4 px corner), the one place the accent is a large fill.
- Code and editors: `ui-monospace, Consolas, monospace`, 12 px; `pre` blocks get `--soft-fill` and radius 12.
- Desk pages load three bundled open fonts (`window/fonts/`, OFL, declared in `desk.css`): Orbitron, Rajdhani 400-700 and Share Tech Mono.
  Which element uses which was not checked for this document.
- Hero words: 600 weight, 30 px with wide tracking (`.08em`), 24 px in a short window. Card titles 15 px / 600.
- Page titles and the top title use 600 weight and `.01em` tracking.

## 6. Components

- **View button / chip switch**: pill-ish, `--soft` text; on = `--accent` fill, `--on-accent` text, `--accent-glow`.
- **Cards** (`#card`, `.a-card`): `--glass` fill, 1 px inset `--glass-edge`, a top inner highlight `--glass-hi`, radius 18-20, `--shadow`.
  The approval/start card appears with a short animation.
- **Say row**: one rounded glass bar holding the input, Send (accent) and Stop (soft fill).
- **Tabs**: Inspector tabs underline in `--accent` when on; Settings sections are `role="tablist"` keys.
- **Tables**: in glass/aurora every header cell has a drag grip; widths are kept per table and column in the page.
- **Foldable cards**: Forex/Notebook cards fold; which are folded is remembered in the browser store (inside try/catch).

## 7. Desk / Forex style ("keys")

The Forex, Notebook, REA, API and guide pages share the **desk** vocabulary (`desk.css`, class `.dv`): a brand block ("SEVEN" over a
small sub-label), an F-key bar (`.fkeys`, numbered buttons) and "keys" with cut corners (`clip-path` polygons: 8 px slants, 7-11 px
chamfers). In aurora and glass the cut corners are replaced with `border-radius: 10px`, and the desk tokens (`--bg, --panel, --fg,
--gain, --loss, --amber, --key, --keygo, --keystop`) are re-set per look so the pages follow the global theme.

Forex page rules Ray has asked for: reports first, manual tools tucked away; a chart that pans and zooms with the mouse, a crosshair
with a price tag, and timeframe / indicator / line keys, with OANDA's feel but not its dark look; views as sub-tabs rather than one
long page.

## 8. The hero avatar and motion

- An orb 170 px wide in the hero strip (112 px when the window is under 760 px tall). The big hero card belongs to the Command Center;
  the same orb moves into the strip on every other page.
- Settings (`avatar-settings.json`): strip on/off and size, `voice_react` (orb follows real voice levels), `backing`, `breathe`,
  `speed`, colour (`custom` with a hue 0-360; the desktop uses 251), line style (`glow`).
- The hero reacts to Seven's replies (a card glow and flash, "Thinking" / "Replying"); the avatar-mood part of that is described in
  the project notes as hard to see.
- `prefers-reduced-motion: reduce` switches the card entrance animation and the orb motion off.

## 9. Responsive and accessibility

- Breakpoints in the code: grids go to one column at **900 px** (Forex, prompts, API) and **760 px** (Command Center); the hero
  shrinks under **760 px height**. There is no phone layout.
- `prefers-color-scheme` picks light or dark unless the Light/Dark button or a palette overrides it.
- The rail has an `aria-label`, the widen button `aria-expanded`, the grips `role="separator"` with labels, are keyboard focusable
  and move 24 px per arrow key; Settings sections are a tablist.

## 10. Known gaps (for a designer)

- Several pages are crowded: Forex and Notebook were split into sub-views and the rail into groups to reduce that; the result has not
  been seen by Ray in his own window.
- The Seven-L1 and classic looks are older than aurora; any new screen should be designed for aurora + the eight palettes.
- Palette colours are light-only; there is no dark version of graphite etc., and the saved theme is "dark" on the desktop. Which
  wins on screen should be checked by looking, not assumed.
- The laptop needs the settings in section 1 before it can be judged against the desktop.
