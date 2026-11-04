"""VoiceControls against the real main window and panel, network faked: the
microphone really opening and closing, what a mute discards, the wake word
raising the window, spoken replies, the header's Mute button and the tray
item staying in step, and the settings the orb left behind.

This is what survived tests/test_orb.py when the orb was removed
(2026-11-04). The face's own tests -- the frameless window's flags, the
click-through hit test, click vs drag, the glyph, the mood, the frame rate,
the sizes, the mic button painted ON the orb -- went with it. Everything
here is about the microphone and the voice, which outlived the face.
"""

import gc
import math
import threading
import weakref

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel

from seven_l1.app import DesktopWindow
from seven_l1.conversation.panel import ConversationPanel
from seven_l1.conversation.threads import ThreadStore
from seven_l1.geometry import load_state, save_state
from seven_l1.sections import Section
from seven_l1.voice.controller import VoiceController
from seven_l1.voice.controls import AVATAR_NOTE, VoiceControls
from seven_l1.voice.mic import MicListener
from seven_l1.voice.speaker import Speaker
from seven_l1.voice.wav import encode_wav


class FakeStatus(QObject):
    health = Signal(dict)
    settings = Signal(dict)
    activity = Signal(dict)

    def start(self): pass
    def stop(self): pass


class FakeClient(QObject):
    done = Signal(str, object)
    line = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.calls = []

    def _rid(self, *call):
        self.calls.append(call)
        return f"r{len(self.calls)}"

    def ask(self, q, skills, history, turn_id=None): return self._rid("ask", q)
    def chat(self, text): return self._rid("chat", text)
    def task(self, text, t, skills, turn_id=None): return self._rid("task", text, t)
    def cancel(self, turn_id): return self._rid("cancel", turn_id)
    def decide(self, aid, allow): return self._rid("decide", aid, allow)
    def stop(self): pass


class FakeWatcher(QObject):
    appeared = Signal(dict)
    vanished = Signal(str)
    answered = Signal(str, str)

    def start(self): pass
    def stop(self): pass
    def pending_count(self): return 0
    def refresh(self): pass


class FakeStream:
    active = True

    def stop(self): self.active = False
    def close(self): self.closed = True


class FakeDevice:
    def __init__(self):
        self.opens = 0
        self.stream = None

    def open(self, callback):
        self.opens += 1
        self.stream = FakeStream()
        return self.stream, 16000


class FakePlayer:
    def __init__(self): self.played = []
    def play(self, path): self.played.append(path)
    def stop(self): pass


def _wav():
    return encode_wav([0.5 * math.sin(i / 4) for i in range(8000)], 16000)


class Rig:
    """No callback here may capture the Rig: a Rig -> window -> lambda ->
    Rig cycle is cyclic garbage holding QWidgets, which the collector can
    free on whatever thread allocates next -- a worker's -- and Qt aborts
    (measured 2026-09-18, the full suite). Capture plain lists instead."""

    def __init__(self, tmp_path, *, avatar=False, saved=None, tray=False, listen=None):
        self.state = tmp_path / "window.json"
        if saved is not None:
            save_state(self.state, saved)
        self.client, self.watcher = FakeClient(), FakeWatcher()
        self.panel = ConversationPanel(self.client, self.watcher,
                                       ThreadStore(tmp_path / "threads.json"))
        self.status = FakeStatus()
        quits = self.quits = []
        self.win = DesktopWindow([Section("Trader", QLabel("t"))], self.status,
                                 state_path=self.state, tray_available=tray,
                                 quit_fn=lambda: quits.append(1), panel=self.panel)
        self.device = FakeDevice()
        spoken = self.spoken = []

        def post(url, body, timeout):
            spoken.append(body["text"])
            return {"wav": _wav()}

        self.player = FakePlayer()
        self.speaker = Speaker("http://ade", post=post, player=self.player,
                               tmpdir=tmp_path)
        self.mic = MicListener(open_stream=self.device.open)
        self.voice = VoiceController(self.panel, base="http://ade",
                                     listen=listen or (lambda *a: {"error": "unused"}))
        self.ctl = VoiceControls(window=self.win, speaker=self.speaker, mic=self.mic,
                                 voice=self.voice, state_path=self.state,
                                 avatar_running=avatar)
        self.win.voice = self.ctl

    def notes(self):
        return [m["text"] for m in self.panel.view_messages("chat") if m.get("role") == "system"]


@pytest.fixture
def rig(qapp, tmp_path):
    r = Rig(tmp_path)
    yield r
    r.ctl.stop()


# ---------------------------------------------------------------- the device


def test_start_opens_the_microphone(rig):
    rig.ctl.start()
    assert rig.mic.running() and rig.device.opens == 1
    assert rig.ctl.mic_act.isChecked()


def test_with_the_avatar_running_the_mic_starts_muted_and_says_why(qapp, tmp_path):
    r = Rig(tmp_path, avatar=True)
    r.ctl.start()
    try:
        assert not r.mic.running() and r.device.opens == 0
        assert not r.ctl.mic_act.isChecked()
        assert AVATAR_NOTE in r.notes()
    finally:
        r.ctl.stop()


def test_muting_closes_the_stream(rig):
    rig.ctl.start()
    rig.ctl.mic_act.setChecked(False)
    assert not rig.mic.running() and rig.device.stream.active is False
    assert load_state(rig.state)["voice"]["mic"] is False
    rig.ctl.mic_act.setChecked(True)
    assert rig.mic.running() and rig.device.opens == 2


def test_quit_releases_the_microphone(rig):
    rig.ctl.start()
    rig.win.quit_app()
    assert not rig.mic.running() and rig.device.stream.active is False
    assert rig.quits == [1]


def test_a_microphone_that_will_not_open_leaves_the_button_on_unmute(qapp, tmp_path):
    r = Rig(tmp_path)

    def broken(callback):
        raise OSError("no input device")

    r.mic._open = broken                                 # the device is gone
    r.win.attach_mic(r.ctl)
    r.ctl.start()
    try:
        assert not r.mic.running() and r.win.mic_button.text() == "Unmute"
        r.win.mic_button.click()
        assert not r.mic.running() and r.win.mic_button.text() == "Unmute"
        assert not r.ctl.mic_act.isChecked()
    finally:
        r.ctl.stop()


# ----------------------------------------------------------------- the voice


def test_the_wake_word_opens_seven(rig):
    """The orb used to flinch and draw wake arcs as well; what is left is
    the part that mattered -- the window comes up with the panel open."""
    rig.ctl.start(open_mic=False)
    rig.win.hide()
    assert rig.voice.on_text("Seven", "whisper") == "opened"
    assert rig.win.isVisible() and rig.win.panel_open()


def test_replies_are_spoken_only_when_speaking_is_on(rig, pump):
    rig.ctl.start(open_mic=False)
    rig.panel.send("hello")
    rig.client.done.emit("r1", {"answer": "All good. More detail follows."})
    pump(lambda: False, timeout=0.2)
    assert rig.spoken == []                                     # default OFF
    rig.ctl.speak_act.setChecked(True)
    rig.panel.send("again")
    rig.client.done.emit("r2", {"answer": "Everything is great. Details."})
    assert pump(lambda: bool(rig.player.played))
    assert rig.spoken == ["Everything is great."]
    assert load_state(rig.state)["voice"]["speak"] is True


def test_muting_discards_speech_already_captured_and_silences_seven(qapp, tmp_path, pump):
    gate = threading.Event()

    def listen(url, body, timeout):
        gate.wait(5)
        return {"text": "Seven, what is pending", "engine": "whisper"}

    r = Rig(tmp_path, listen=listen)
    r.ctl.start()
    try:
        r.ctl.speak_act.setChecked(True)
        r.mic.utterance.emit({"samples": [0.1] * 1600, "rate": 16000})   # in flight
        r.mic.utterance.emit({"samples": [0.1] * 1600, "rate": 16000})   # waiting
        hushed = []
        r.speaker.hush = lambda: hushed.append(1)
        r.ctl.mic_act.setChecked(False)
        gate.set()
        pump(lambda: not r.voice._inflight, timeout=3)
        pump(lambda: False, timeout=0.2)
        assert r.client.calls == []               # nothing asked after the mute
        assert hushed and r.win.isHidden()
    finally:
        r.ctl.stop()


def test_an_utterance_arriving_after_mute_is_dropped(rig):
    rig.ctl.start()
    rig.ctl.mic_act.setChecked(False)
    rig.mic.utterance.emit({"samples": [0.1] * 1600, "rate": 16000})
    assert rig.voice._inflight is False


def test_seven_stop_silences_the_reply(rig):
    rig.ctl.start(open_mic=False)
    hushed = []
    rig.speaker.hush = lambda: hushed.append(1)
    rig.voice.hush_requested.disconnect()
    rig.voice.hush_requested.connect(rig.speaker.hush)
    assert rig.voice.on_text("Seven, stop.", "whisper") == "hushed"
    assert hushed == [1] and rig.client.calls == []


# -- the mute button (Ray, 2026-09-18: "i need a mute botton") ----------------


def test_the_header_has_a_mute_button_that_mutes_and_unmutes(rig):
    rig.win.attach_mic(rig.ctl)
    rig.ctl.start()
    button = rig.win.mic_button
    assert button.isVisibleTo(rig.win) and button.text() == "Mute"
    button.click()
    assert not rig.mic.running() and rig.device.stream.active is False
    assert button.text() == "Unmute" and button.property("muted") is True
    assert not rig.ctl.mic_act.isChecked()                # the tray item agrees
    assert load_state(rig.state)["voice"]["mic"] is False  # and it is remembered
    button.click()
    assert rig.mic.running() and button.text() == "Mute" and rig.ctl.mic_act.isChecked()


def test_the_tray_item_and_the_button_stay_in_step(rig):
    rig.win.attach_mic(rig.ctl)
    rig.ctl.start()
    rig.ctl.mic_act.setChecked(False)                    # muted from the tray
    assert rig.win.mic_button.text() == "Unmute"
    rig.ctl.mic_act.setChecked(True)
    assert rig.win.mic_button.text() == "Mute"


def test_muted_for_the_avatar_the_button_says_unmute(qapp, tmp_path):
    r = Rig(tmp_path, avatar=True)
    r.win.attach_mic(r.ctl)
    r.ctl.start()
    try:
        assert r.win.mic_button.text() == "Unmute"
        r.win.mic_button.click()                         # Ray's explicit choice
        assert r.mic.running() and r.win.mic_button.text() == "Mute"
    finally:
        r.ctl.stop()


def test_without_voice_there_is_no_mute_button(qapp, tmp_path):
    win = DesktopWindow([Section("Trader", QLabel("t"))], FakeStatus(),
                        state_path=tmp_path / "w.json", tray_available=False)
    assert not win.mic_button.isVisibleTo(win)


# -- settings ----------------------------------------------------------------


def test_voice_settings_and_window_state_share_window_json(qapp, tmp_path):
    r = Rig(tmp_path, saved={"voice": {"speak": True, "mic": False}})
    r.ctl.start()
    try:
        assert r.ctl.speak_act.isChecked()
        assert not r.mic.running() and r.device.opens == 0      # remembered mute
        r.win.save_state()                                      # the window's own save
        state = load_state(r.state)
        assert state["voice"]["speak"] is True and "w" in state  # neither clobbers the other
    finally:
        r.ctl.stop()


def test_the_orbs_old_settings_are_carried_over_once_then_the_block_is_dropped(qapp, tmp_path):
    """Speak and mic outlived the orb; x, y, size, visible and backing
    described the face and did not. Reading the old block means the first
    launch after the removal does not silently reset the two that matter."""
    r = Rig(tmp_path, saved={"orb": {"x": 40, "y": 50, "size": "S", "visible": True,
                                     "speak": True, "mic": False, "backing": False}})
    try:
        assert r.ctl.speak_on is True and r.ctl.mic_wanted is False
        r.ctl.save()
        state = load_state(r.state)
        assert state["voice"] == {"speak": True, "mic": False}
        assert "orb" not in state           # migrated, and the face's keys are gone
    finally:
        r.ctl.stop()


def test_a_voice_block_wins_over_a_stale_orb_block(qapp, tmp_path):
    r = Rig(tmp_path, saved={"orb": {"speak": True, "mic": False},
                             "voice": {"speak": False, "mic": True}})
    try:
        assert r.ctl.speak_on is False and r.ctl.mic_wanted is True
    finally:
        r.ctl.stop()


# -- lifetime ----------------------------------------------------------------


def test_the_controller_does_not_keep_the_main_window_alive(qapp, tmp_path):
    """The window holds the controller; the controller holds the window
    weakly. Were it strong, the pair would be cyclic garbage."""
    r = Rig(tmp_path)
    ref = weakref.ref(r.win)
    gc.disable()
    try:
        r.win = None
        assert ref() is None
        assert r.ctl.window is None
        r.ctl.open_seven()                  # a late wake finds no window: harmless
    finally:
        gc.enable()
