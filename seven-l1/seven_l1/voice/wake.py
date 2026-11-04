"""The wake word: "Seven".

Replaces Ade Desktop's rule, which was the avatar's verbatim
(adeos/avatar/ui.js WAKE, `ad[ae]y?`) and covered the four spellings
"Ade", "Hey Ade", "Ada" and "Aday" that the live recogniser was MEASURED
to produce for one spoken token (by the avatar, 2026-08-27).

**This rule carries no such measurement.** Nobody has yet checked what
whisper actually returns for a spoken "Seven" on this microphone, so the
variants below are reasoned, not observed:

- `sevens?` -- the plural is the obvious mis-hear, and this laptop is
  called SevensLaptop, so "Sevens" is likely in the recogniser's prior.
- an optional "L1" tail, spelled `l1`, `l one` or `el one`, because the
  product is Seven-L1 and saying it in full must not swallow the command.
  Without it, "Seven L1, status" would wake with the command "L1, status".

A separator and more text are still required, so "Sevenfold" never wakes
it -- the same guard "Adelaide" needed before.

NOTE: adeos/avatar still wakes on "Ade". The two faces no longer share a
wake word, and ui.js was deliberately not touched by this rename.

WAKE and the controller's WAKE_ONLY are built from ONE stem here. They were
two independent regexes before, and the rename found that out the hard way:
WAKE moved to "Seven" while the copy in controller.py still said `ad[ae]y?`,
so the bare word would have gone on waking to the old name with nothing to
say it had been missed.
"""

from __future__ import annotations

import re

# Everything up to the separator. WAKE requires text after it; WAKE_ONLY
# (controller.py) requires end-of-string instead.
WAKE_STEM = (
    r"^\s*(?:hey\s+|ok\s+)?sevens?"
    r"(?:\s*[- ]?\s*(?:l\s*1|l\s*one|el\s*one))?"
    r"\s*[,.!?:-]?"
)

WAKE = re.compile(WAKE_STEM + r"\s+", re.I)


def strip_wake(text) -> str | None:
    """The command after the wake word, or None if it was not woken."""
    if text is None:
        return None
    m = WAKE.match(str(text))
    return str(text)[m.end():].strip() if m else None
