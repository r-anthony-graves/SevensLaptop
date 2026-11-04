"""The Lotto panel: choose a game, a ticket and a number of draws, then read
the exact odds of every prize tier beside what the simulation actually hit.

A native rewrite of PythonLotto's Textual UI over the same core library.
Three rules come with it from that UI, each a real bug or risk there:
simulation runs off the GUI thread, stop() cancels and waits, and the
progress bar resets on a game switch.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QProgressBar, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from seven_l1.sections.lotto.client import LottoClient
from seven_l1.sections.pm.panel import ERROR_STYLE, MUTED_STYLE

DEFAULT_TRIALS = 100_000          # the terminal app's default
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return table


def _fill(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            item = QTableWidgetItem(text)
            if c:                               # every column but the tier is a number
                item.setTextAlignment(_RIGHT)
            table.setItem(r, c, item)


class LottoPanel(QWidget):
    def __init__(self, client: LottoClient | None = None, parent=None) -> None:
        super().__init__(parent)
        from pythonlotto import MAX_TRIALS, PRESETS

        self.client = client if client is not None else LottoClient()
        self.client.setParent(self)
        self._engine = None
        self._ticket = None
        self._rid: str | None = None            # the run whose result we still want

        self.game = QComboBox()
        for key, config in PRESETS.items():
            self.game.addItem(config.name, key)
        self.rules = QLabel()
        self.rules.setStyleSheet(MUTED_STYLE)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Type a ticket, e.g. 7 12 33 41 68 | 9, and press Enter")
        self.quick = QPushButton("Quick pick")
        self.ticket_label = QLabel("No ticket yet")

        self.trials = QSpinBox()
        self.trials.setRange(1, MAX_TRIALS)
        self.trials.setGroupSeparatorShown(True)
        self.trials.setValue(DEFAULT_TRIALS)
        self.trials.setSuffix(" draws")
        self.run = QPushButton("Run")
        self.cancel = QPushButton("Cancel")
        self.cancel.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, DEFAULT_TRIALS)
        self.progress.setValue(0)
        self.status = QLabel()
        self.status.setWordWrap(True)

        self.odds = _table(["Tier", "Probability", "Odds"])
        self.results = _table(["Tier", "Hits", "Observed", "Expected"])

        top = QHBoxLayout()
        top.addWidget(QLabel("Game"))
        top.addWidget(self.game)
        top.addWidget(self.rules, 1)
        ticket = QHBoxLayout()
        ticket.addWidget(self.entry, 1)
        ticket.addWidget(self.quick)
        ticket.addWidget(self.ticket_label)
        run = QHBoxLayout()
        run.addWidget(self.trials)
        run.addWidget(self.run)
        run.addWidget(self.cancel)
        run.addWidget(self.progress, 1)
        tables = QHBoxLayout()
        for title, table in (("Exact odds", self.odds), ("Simulation", self.results)):
            col = QVBoxLayout()
            head = QLabel(title)
            head.setStyleSheet("font-weight:600;")
            col.addWidget(head)
            col.addWidget(table)
            tables.addLayout(col)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addLayout(ticket)
        root.addLayout(run)
        root.addWidget(self.status)
        root.addLayout(tables, 1)

        self.game.currentIndexChanged.connect(self._on_game)
        self.quick.clicked.connect(self.quick_pick)
        self.entry.returnPressed.connect(self._on_entry)
        self.run.clicked.connect(self.start)
        self.cancel.clicked.connect(self.request_cancel)
        self.client.line.connect(self._on_progress)
        self.client.done.connect(self._on_done)
        self._on_game()

    # -- game and ticket ------------------------------------------------------

    def _on_game(self) -> None:
        from pythonlotto import PRESETS, LotteryEngine, all_tiers, jackpot_odds

        config = PRESETS[self.game.currentData()]
        self._engine = LotteryEngine(config)   # the OS CSPRNG: seeding is the CLI's alone
        self.rules.setText(
            f"{config.describe()}  ·  jackpot 1 in {jackpot_odds(config).one_in:,.0f}"
            f"  ·  {config.total_combinations:,} combinations")
        _fill(self.odds, [[t.label(), f"{float(t.probability):.3e}", f"1 in {t.one_in:,.0f}"]
                          for t in all_tiers(config)])
        self.results.setRowCount(0)
        # Rule 3: a bar left part-filled from the last game reads as progress
        # against this one. It shipped that way in the TUI (fixed in 62616a2).
        self.progress.setRange(0, self.trials.value())
        self.progress.setValue(0)
        self._set_ticket(None)
        self._say("")

    def _set_ticket(self, ticket) -> None:
        self._ticket = ticket
        self.ticket_label.setText(str(ticket) if ticket is not None else "No ticket yet")

    def quick_pick(self) -> None:
        self._set_ticket(self._engine.quick_pick())
        self._say("")

    def _on_entry(self) -> None:
        from pythonlotto import LottoError, Ticket

        text = self.entry.text().strip()
        if not text:
            return
        try:
            self._set_ticket(Ticket.parse(self._engine.config, text))
        except LottoError as exc:
            self._say(str(exc), error=True)    # written for the user: shown as-is
            return
        self.entry.clear()
        self._say("")

    # -- running --------------------------------------------------------------

    @property
    def busy(self) -> bool:
        return self._rid is not None

    def start(self) -> None:
        if self.busy:
            return
        if self._ticket is None:
            self.quick_pick()
        trials = self.trials.value()
        self.progress.setRange(0, trials)
        self.progress.setValue(0)
        self.results.setRowCount(0)
        self._busy(True)
        self._say(f"Simulating {trials:,} draws...")
        self._rid = self.client.simulate(self._engine, self._ticket, trials) or None
        if self._rid is None:                  # the client was already stopped
            self._busy(False)

    def request_cancel(self) -> None:
        if self.busy:
            self.client.cancel()
            self._say("Cancelling...")

    def _on_progress(self, rid: str, text: str) -> None:
        if rid != self._rid:
            return
        completed, total = (int(n) for n in text.split())
        self.progress.setRange(0, total)
        self.progress.setValue(completed)

    def _on_done(self, rid: str, reply: dict) -> None:
        if rid != self._rid:
            return
        self._rid = None
        self._busy(False)
        if "error" in reply:
            self._say(reply["error"], error=True)
            return
        result = reply["result"]
        self._render(result)
        self.progress.setValue(result.trials)
        verb = "Cancelled after" if result.cancelled else "Completed"
        self._say(f"{verb} {result.trials:,} draws in {result.elapsed_seconds:.2f}s"
                  f" ({result.trials_per_second:,.0f}/s)  ·  jackpots: {result.jackpots:,}")

    def _render(self, result) -> None:
        from pythonlotto import all_tiers, tier_probability

        config = result.config
        rows = []
        for tier in all_tiers(config):
            m, b = tier.main_matches, tier.bonus_matches
            expected = float(tier_probability(config, m, b)) * result.trials
            rows.append([tier.label(), f"{result.count(m, b):,}",
                         f"{result.observed_rate(m, b):.6f}", f"{expected:,.2f}"])
        _fill(self.results, rows)

    def _busy(self, on: bool) -> None:
        # One run at a time, and the game is frozen under it: switching mid-run
        # would show one game's odds beside another game's results.
        for w in (self.game, self.entry, self.quick, self.trials, self.run):
            w.setEnabled(not on)
        self.cancel.setEnabled(on)

    def _say(self, text: str, error: bool = False) -> None:
        self.status.setStyleSheet(ERROR_STYLE if error else MUTED_STYLE)
        self.status.setText(text)

    def stop(self) -> None:
        """Rule 2: cancel a live run and wait for it, so it cannot outlive the app."""
        self.client.stop()
