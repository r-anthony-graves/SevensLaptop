"""VoiceControls: the microphone, the spoken reply, and their two tray items.

This is what was left of OrbController once the orb was removed
(2026-11-04). The face it drew -- the glyph, the mood, the frame timer, the
size, the placement, the click-through hit test -- is gone. What that class
ALSO carried, and what the app still needs, is here:

    the microphone      opened and closed, and what it IS doing
    an utterance        handed to VoiceController, unless the mic just shut
    the wake word       VoiceController's open_requested raises the window
    a spoken reply      Speaker, when "Speak Seven's replies" is on
    two tray items      Microphone, Speak Seven's replies

Nothing here draws, so there is no timer and no frame budget. The orb's
`mood` fed only the glyph; health, activity, approvals and busy-state were
wired in for it alone, and all of that went with the face.

It holds the main window WEAKLY: the window keeps this object (to stop it
at quit), and a strong reference back would make the pair cyclic garbage --
the class of object whose collection mid-emit crashed PySide in piece 1.
"""

from __future__ import annotations

import logging
import weakref
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction

from seven_l1.geometry import load_state, save_state

log = logging.getLogger("seven_l1.voice.controls")

AVATAR_NOTE = ("The Electron avatar is running and listening. The microphone "
               "starts muted so one wake word isn't answered twice; unmute it "
               "with the Mute button or from the tray.")
MIC_FAILED = "The microphone could not be opened ({why}). Seven stays muted."


class VoiceControls(QObject):
    mic_state = Signal(bool)        # the microphone IS (True) or is not listening

    def __init__(self, *, window, speaker, mic, voice, state_path: Path,
                 avatar_running: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._window = weakref.ref(window)
        self.speaker, self.mic, self.voice = speaker, mic, voice
        self.panel = window.panel
        self._state_path = Path(state_path)

        self.speak_on, self.mic_wanted = self._load_settings()
        self.avatar_running = bool(avatar_running)

        self._build_actions(window)

        self.panel.reply_landed.connect(self._on_reply)
        self.speaker.failed.connect(self.panel.note)
        self.mic.utterance.connect(self._on_utterance)
        self.mic.failed.connect(self._on_mic_failed)
        self.voice.open_requested.connect(self.open_seven)
        self.voice.hush_requested.connect(self.speaker.hush)
        # voice.wake_heard is deliberately not connected: it existed so the
        # glyph could draw wake arcs and the mood could flinch. The window
        # is raised by open_requested, which VoiceController emits with it.

    # -- settings -------------------------------------------------------------

    def _load_settings(self) -> tuple[bool, bool]:
        """speak (default OFF) and mic (default ON).

        Read from "voice", falling back to the orb's old "orb" block so the
        two settings that outlived the orb are not silently reset on the
        first launch after it was removed. Everything else in that block --
        x, y, size, visible, backing -- described the face and is dropped.
        """
        state = load_state(self._state_path)
        block = state.get("voice")
        if not isinstance(block, dict):
            block = state.get("orb")
            block = block if isinstance(block, dict) else {}
        return block.get("speak") is True, block.get("mic") is not False

    def save(self) -> None:
        state = load_state(self._state_path)
        state["voice"] = {"speak": self.speak_on, "mic": self.mic_wanted}
        state.pop("orb", None)          # the face's keys, migrated and done with
        save_state(self._state_path, state)

    # -- menu -----------------------------------------------------------------

    @property
    def window(self):
        return self._window()

    def _build_actions(self, window) -> None:
        """Two checkable items, put in the tray's menu.

        The orb had a context menu of its own (Open, Size, Backing glow,
        Hide orb, Quit) and these two sat in it as well. With no orb there
        is one home for them, and Show Seven / Quit are the tray's already.
        """
        self.speak_act = QAction("Speak Seven's replies", self, checkable=True)
        self.speak_act.setChecked(self.speak_on)
        self.speak_act.toggled.connect(self.set_speak)
        self.mic_act = QAction("Microphone", self, checkable=True)
        self.mic_act.toggled.connect(self.set_mic)
        tray = getattr(window, "tray", None)
        if tray is not None and tray.contextMenu() is not None:
            # after "Show Seven", before the separator and Quit
            tmenu = tray.contextMenu()
            before = tmenu.actions()[1] if len(tmenu.actions()) > 1 else None
            for act in (self.speak_act, self.mic_act):
                tmenu.insertAction(before, act)

    # -- lifecycle ------------------------------------------------------------

    def start(self, *, open_mic: bool = True) -> None:
        """Open the microphone unless it should start muted. open_mic=False
        (the smoke run) never touches the audio device."""
        muted_for_avatar = self.avatar_running and self.mic_wanted
        if muted_for_avatar:
            self.panel.note(AVATAR_NOTE)
        self.mic_act.blockSignals(True)
        self.mic_act.setChecked(self.mic_wanted and not muted_for_avatar)
        self.mic_act.blockSignals(False)
        if self.mic_act.isChecked() and (not open_mic or not self.mic.start()):
            self._uncheck_mic()
        self._announce_mic()

    def stop(self) -> None:
        self.save()
        self.mic.stop()
        self.voice.stop()
        self.speaker.close()

    # -- what it hears and says -----------------------------------------------

    def _on_utterance(self, utt) -> None:
        # A block captured just before a mute can still be queued: a closed
        # microphone hears nothing, including its last breath.
        if self.mic.running():
            self.voice.on_utterance(utt)

    def _on_mic_failed(self, why: str) -> None:
        self.panel.note(MIC_FAILED.format(why=why))

    def _on_reply(self, text: str) -> None:
        if self.speak_on:
            self.speaker.speak(text)

    def open_seven(self) -> None:
        window = self.window
        if window is None:
            return
        window.show_and_raise()
        window.set_panel_open(True)
        self.panel.focus_input()

    # -- actions --------------------------------------------------------------

    def set_speak(self, on: bool) -> None:
        self.speak_on = bool(on)
        if not on:
            self.speaker.hush()
        self.save()

    def set_mic(self, on: bool) -> None:
        self.mic_wanted = bool(on)
        if on:
            if not self.mic.start():
                self._uncheck_mic()
                return
        else:
            self.mic.stop()
            self.voice.discard()        # nothing captured before the mute is acted on
            self.speaker.hush()         # and Seven stops talking too
        self.save()
        self._announce_mic()

    def toggle_mic(self) -> None:
        """The header's Mute button: flip what the microphone IS doing (not
        what the menu last said), through the same path as the tray item."""
        want = not self.mic.running()
        self.mic_act.blockSignals(True)
        self.mic_act.setChecked(want)
        self.mic_act.blockSignals(False)
        self.set_mic(want)

    def _uncheck_mic(self) -> None:
        self.mic_act.blockSignals(True)
        self.mic_act.setChecked(False)
        self.mic_act.blockSignals(False)
        self._announce_mic()

    def _announce_mic(self) -> None:
        self.mic_state.emit(self.mic.running())
