"""The Lotto panel over the real pythonlotto core: the odds it shows are the
library's, a run happens off the GUI thread and can be cancelled, stop()
cancels AND waits, and the three rules carried over from PythonLotto's TUI
(worker thread, stop waits, bar resets on game switch) each hold."""

import gc
import sys
import time
import weakref

import pytest

from seven_l1.sections.lotto.panel import LottoPanel


@pytest.fixture
def panel(qapp):
    p = LottoPanel()
    yield p
    p.stop()                     # never leave a simulation running between tests


def _select(panel, key):
    panel.game.setCurrentIndex(panel.game.findData(key))


def _run(panel, pump, trials, timeout=30.0):
    panel.trials.setValue(trials)
    panel.start()
    assert pump(lambda: not panel.busy, timeout), "the run never finished"


# -- the section ---------------------------------------------------------------

def test_the_section_is_lotto_and_its_stop_is_the_panel_s(qapp):
    from seven_l1.sections.lotto import build_lotto_section
    section = build_lotto_section()
    try:
        assert section.name == "Lotto"
        assert section.stop == section.widget.stop
    finally:
        section.stop()


def test_lotto_follows_pm_and_qa_in_the_rail(qapp):
    from seven_l1.sections import build_sections
    sections = build_sections()
    try:
        assert [s.name for s in sections] == ["PM", "QA", "Lotto"]
    finally:
        for s in sections:
            if s.stop:
                s.stop()


# -- odds --------------------------------------------------------------------------

def test_the_odds_table_is_the_library_s_exact_odds(panel):
    from pythonlotto import PRESETS, all_tiers
    _select(panel, "powerball")
    tiers = all_tiers(PRESETS["powerball"])
    assert panel.odds.rowCount() == len(tiers)
    assert panel.odds.item(0, 0).text() == "5 + 1"
    assert panel.odds.item(0, 2).text() == "1 in 292,201,338"
    assert "292,201,338 combinations" in panel.rules.text()


def test_every_preset_fills_the_odds_table(panel):
    from pythonlotto import PRESETS, all_tiers
    for key, config in PRESETS.items():
        _select(panel, key)
        assert panel.odds.rowCount() == len(all_tiers(config)), key


def test_switching_game_resets_the_progress_bar(panel):
    """Rule 3: a part-filled bar from the last game read as progress against
    the new one. It shipped that way in the TUI and was fixed in 62616a2."""
    _select(panel, "powerball")
    panel.progress.setRange(0, 100)
    panel.progress.setValue(60)
    _select(panel, "euromillions")
    assert panel.progress.value() == 0


def test_the_trials_box_is_capped_at_the_library_s_limit(panel):
    from pythonlotto import MAX_TRIALS
    assert panel.trials.maximum() == MAX_TRIALS


# -- tickets -------------------------------------------------------------------------

def test_quick_pick_makes_a_ticket_valid_for_the_game(panel):
    from pythonlotto import Ticket
    _select(panel, "euromillions")
    panel.quick_pick()
    text = panel.ticket_label.text()
    assert Ticket.parse(panel._engine.config, text) == panel._ticket


def test_a_typed_ticket_is_parsed_by_the_library(panel):
    _select(panel, "powerball")
    panel.entry.setText("7 12 33 41 68 | 9")
    panel._on_entry()
    assert panel._ticket is not None
    assert panel.entry.text() == ""


def test_a_bad_ticket_shows_the_library_s_own_message(panel):
    """Every LottoError's message is written for the user: shown as-is."""
    from pythonlotto import LottoError, Ticket
    _select(panel, "powerball")
    bad = "1 2 3 | 9"
    with pytest.raises(LottoError) as exc:
        Ticket.parse(panel._engine.config, bad)
    panel.entry.setText(bad)
    panel._on_entry()
    assert panel.status.text() == str(exc.value)
    assert panel._ticket is None


# -- running -------------------------------------------------------------------------

def test_a_run_fills_the_results_and_accounts_for_every_draw(panel, pump):
    _select(panel, "lotto-6-49")
    _run(panel, pump, 20_000)
    rows = panel.results.rowCount()
    assert rows == panel.odds.rowCount()
    hits = sum(int(panel.results.item(r, 1).text().replace(",", "")) for r in range(rows))
    assert hits == 20_000
    assert panel.status.text().startswith("Completed 20,000 draws")
    assert panel.progress.value() == 20_000


def test_a_run_without_a_ticket_quick_picks_one(panel, pump):
    assert panel._ticket is None
    _run(panel, pump, 5_000)
    assert panel._ticket is not None


def test_the_controls_are_frozen_while_a_run_is_live(panel, pump):
    """Switching game mid-run would put one game's odds beside another's hits."""
    panel.trials.setValue(2_000_000)
    panel.start()
    try:
        assert not panel.game.isEnabled() and not panel.run.isEnabled()
        assert panel.cancel.isEnabled()
    finally:
        panel.request_cancel()
        pump(lambda: not panel.busy, 10)
    assert panel.game.isEnabled() and panel.run.isEnabled()
    assert not panel.cancel.isEnabled()


def test_cancel_stops_a_run_early_and_says_so(panel, pump):
    panel.trials.setValue(10_000_000)
    panel.start()
    assert pump(lambda: panel.progress.value() > 0, 10), "no progress arrived"
    panel.request_cancel()
    assert pump(lambda: not panel.busy, 10)
    assert panel.status.text().startswith("Cancelled after")
    assert panel.progress.value() < 10_000_000


def test_the_run_happens_off_the_gui_thread(panel, pump):
    """Rule 1: the GUI thread keeps turning over WHILE a run is live.

    Counting ticks alone would pass a run on the GUI thread: start() would
    block until the run ended, then the ticks would arrive after it. So this
    asserts that start() returns at once with the run still going, and that
    no gap between ticks, measured while it runs, is longer than a stutter.
    """
    from PySide6.QtCore import QTimer
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start(20)
    try:
        panel.trials.setValue(2_000_000)
        t0 = time.monotonic()
        panel.start()
        assert time.monotonic() - t0 < 0.5, "start() blocked: the run is on the GUI thread"
        assert panel.busy, "the run finished inside start()"
        pump(lambda: len(ticks) >= 25, 5)
        still_running = panel.busy
    finally:
        timer.stop()
        panel.request_cancel()
        pump(lambda: not panel.busy, 10)
    assert still_running, "the run ended before the GUI was measured under it"
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert max(gaps) < 0.25, f"the GUI stalled for {max(gaps):.2f}s under a run"


def test_stop_cancels_a_live_run_and_waits_for_it(panel, pump):
    """Rule 2: the app hides to the tray and quits from there, so a live run
    must not outlive the window. Cancellation lands within one 5,000-draw
    chunk -- about 25 ms."""
    panel.trials.setValue(10_000_000)
    panel.start()
    assert pump(lambda: panel.progress.value() > 0, 10)
    t0 = time.monotonic()
    panel.stop()
    assert time.monotonic() - t0 < 1.0
    assert not panel.client.running
    pump(lambda: False, 0.2)              # anything queued would land now
    assert not panel.status.text().startswith(("Completed", "Cancelled"))


def test_a_stopped_panel_starts_nothing(panel):
    panel.stop()
    panel.start()
    assert not panel.busy and not panel.client.running


# -- lifetime and packaging ----------------------------------------------------------

def test_a_dropped_panel_is_freed_at_once(qapp):
    panel = LottoPanel()
    panel.quick_pick()
    ref = weakref.ref(panel)
    gc.disable()
    try:
        del panel
        assert ref() is None
    finally:
        gc.enable()


def test_the_panel_never_loads_textual(panel):
    """The desktop installs pythonlotto without its [tui] extra; the panel
    must not need it."""
    assert not any(m == "textual" or m.startswith("textual.") for m in sys.modules)
