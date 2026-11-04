"""python -m seven_l1 -- the app.

    python -m seven_l1            run it (a second launch brings the
                                     running one forward and exits)
    python -m seven_l1 --smoke    build it headless, poll for a moment,
                                     print what it saw as JSON, write a PNG
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger("seven_l1")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="seven_l1")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--smoke-wait", type=int, default=4000)
    parser.add_argument("--smoke-out", default="smoke.png")
    return parser.parse_args(argv)


def setup_logging(directory: Path) -> None:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / "desktop.log",
                                      maxBytes=1_000_000, backupCount=3,
                                      encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # httpx logs every request at INFO -- the trader and the header poll
    # about once a second, which buried the transitions this log is for.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def configure_app(app) -> None:
    app.setApplicationName("Seven-L1")
    # Close hides to the tray; DesktopWindow quits explicitly when it must.
    app.setQuitOnLastWindowClosed(False)


def claim_instance(guard, lock_dir: Path, *, wait_s: float = 2.0) -> bool:
    """True if this launch should run. False if another instance is running
    (or starting) and has been asked to show itself instead."""
    if guard.notify_running():
        log.info("already running: asked it to show itself")
        return False
    if guard.acquire(lock_dir):
        if not guard.listen():
            log.warning("single-instance listen failed; continuing anyway")
        return True
    # The lock is held but nobody answered: another launch began a moment
    # ago and is not listening yet. Give it a moment, then hand it "show".
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        time.sleep(0.1)
        if guard.notify_running(timeout_ms=200):
            log.info("already starting: asked it to show itself")
            return False
    log.warning("another instance holds the lock and never answered; "
                "not starting a second one (run-seven.ps1 -Stop clears it)")
    return False


def connect_instance(guard, win) -> None:
    guard.show_requested.connect(win.show_and_raise)


def build_window(*, state_path: Path, quit_fn=None, orb: bool = True,
                 avatar_running: bool | None = None):
    from seven_l1.ade_status import AdeStatusClient
    from seven_l1.app import DesktopWindow
    from seven_l1.conversation.approvals import ApprovalWatcher
    from seven_l1.conversation.client import ConversationClient
    from seven_l1.conversation.panel import ConversationPanel
    from seven_l1.conversation.sessions import GENERAL, ApprovalRouter, session_for
    from seven_l1.conversation.threads import ThreadStore
    from seven_l1.sections import build_sections
    from seven_l1.workspace.active import ActiveProject

    # A chat per section (Ray, 2026-09-18): each with its own thread file
    # (beside window.json -- the smoke run passes a temp state_path, so it
    # never touches the real conversations), Ade OS topic and terminal
    # session. ONE approval watcher, routed to the chat whose turn asked.
    approvals = ApprovalWatcher()
    router = ApprovalRouter(approvals)

    def chat(name):
        spec = session_for(name)
        store = ThreadStore(Path(state_path).with_name(spec.threads_file))
        client = ConversationClient(topic=spec.topic, session=spec.terminal)
        conversation = ConversationPanel(client, router.watcher_for(name), store)
        router.bind(name, conversation)
        return conversation

    panel = chat(GENERAL)
    active = ActiveProject(state_path)
    sections = build_sections(active)
    side = {section.name: chat(section.name) for section in sections}
    win = DesktopWindow(sections, AdeStatusClient(),
                        state_path=state_path, quit_fn=quit_fn, panel=panel,
                        side_panels=side, approvals=approvals)
    router.setParent(win)
    approvals.setParent(win)
    win.approval_router = router
    for section in sections:
        request = getattr(section.widget, "section_requested", None)
        if request is not None:
            request.connect(win.show_section)
    if orb:
        win.orb_controller = build_orb(win, state_path, avatar_running)
        win.attach_mic(win.orb_controller)
    return win


def build_orb(win, state_path: Path, avatar_running: bool | None = None):
    """The orb and its voice (piece 3). Nothing here opens a device or
    shows a window until OrbController.start()."""
    from seven_l1.orb.avatar_probe import avatar_running as probe
    from seven_l1.orb.controller import OrbController
    from seven_l1.orb.glyph import GlyphRenderer
    from seven_l1.orb.mood import Mood
    from seven_l1.orb.window import OrbWindow
    from seven_l1.voice.controller import VoiceController
    from seven_l1.voice.mic import MicListener
    from seven_l1.voice.speaker import Speaker

    if avatar_running is None:
        avatar_running = probe()
    return OrbController(
        window=win, orb=OrbWindow(), renderer=GlyphRenderer(), mood=Mood(),
        speaker=Speaker(), mic=MicListener(), voice=VoiceController(win.panel),
        state_path=Path(state_path), avatar_running=avatar_running)


def smoke_report(win) -> dict:
    from seven_l1.conversation.sessions import GENERAL

    # General (the conversation, full size) leads the rail when there is a panel.
    registry = ((["General"] if win.panel is not None else [])
                + [s.name for s in win.sections])
    # `ok` is the STRUCTURE only: DOWN is a correctly rendered state, so a
    # smoke run against a stopped Ade OS still passes. Whether an answer
    # arrived at all is reported separately, as `ade_polled`.
    ok = bool(registry) and win.section_names() == registry
    return {
        "ok": ok,
        "sections": win.section_names(),
        "ade_polled": win.ade_pill.label != "—",
        "ade_pill": win.ade_pill.text(),
        "ade_tooltip": win.ade_pill.toolTip(),
        "brain": win.brain_label.text(),
        "panel": ({"tabs": [win.panel.tabs.tabText(i)
                            for i in range(win.panel.tabs.count())],
                   "open": win.panel_open()} if win.panel is not None else None),
        "chats": ([GENERAL] if win.panel is not None else []) + list(win.side_panels),
        "chat_topics": sorted({c.client.topic for c in win.all_panels()}),
    }


def run_smoke(app, args) -> int:
    # Never the real window.json: a smoke run must not move Ray's window.
    state = Path(tempfile.mkdtemp(prefix="seven-l1-smoke-")) / "window.json"
    win = build_window(state_path=state, quit_fn=app.quit, avatar_running=False)
    win.start()
    win.show()
    win.orb_controller.start(open_mic=False)   # never the real microphone
    deadline = time.monotonic() + max(0, args.smoke_wait) / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    report = smoke_report(win)
    out = Path(args.smoke_out)
    report["png_written"] = bool(win.grab().save(str(out)))
    report["png"] = str(out.resolve())
    ctl = win.orb_controller
    frame = ctl.orb.frame
    orb_png = out.with_name(out.stem + "-orb" + out.suffix)
    report["orb"] = {
        "shown": ctl.orb.isVisible(),
        "frame": None if frame is None else [frame.width(), frame.height()],
        "online": ctl.online,
        "mood": ctl.mood.frame().get("mood"),
        "mic_open": ctl.mic.running(),
        "mute_button": win.mic_button.text() if win.mic_button.isVisibleTo(win) else None,
        "png_written": bool(frame is not None and frame.save(str(orb_png))),
        "png": str(orb_png.resolve()),
    }
    win.quit_app()
    print(json.dumps(report, indent=2))
    log.info("smoke: ok=%s", report["ok"])
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        # Headless Qt ships no fonts: without this every letter in the smoke
        # PNG is an empty box, and the picture proves only the layout.
        if os.name == "nt":
            os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(
                os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

    from PySide6.QtWidgets import QApplication

    from seven_l1.geometry import state_dir
    from seven_l1.single_instance import SingleInstance

    app = QApplication(sys.argv[:1])
    configure_app(app)
    directory = state_dir()
    setup_logging(directory)
    log.info("starting (smoke=%s)", args.smoke)

    if args.smoke:
        return run_smoke(app, args)

    guard = SingleInstance()
    if not claim_instance(guard, directory):
        return 0

    win = build_window(state_path=directory / "window.json")
    connect_instance(guard, win)
    win.start()
    win.show_initial()
    win.orb_controller.start()
    code = app.exec()
    guard.release()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
