"""The sections the rail lists. Only sections that EXIST are listed: a
greyed-out button for an unbuilt section reads as broken.

Seven-L1 began as the laptop fork of Ade Desktop (`ade-desktop-laptop`,
which no longer exists on GitHub -- its history is archived under
F:\\Ade Storage\\backups). That fork's upstream also built Trader, Path and
Code; Ray does not use those on the laptop, so they were deleted here
outright rather than hidden behind a switch. Trader
imported the tradinglocal checkout's widgets into this process and Path reads a
server that is not on this machine -- both only ever rendered placeholders
here. General comes from the conversation panel, not this list.

Lotto (2026-09-20) is PythonLotto moved in: its odds and simulation core,
drawn natively in place of its Textual UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


@dataclass
class Section:
    name: str
    widget: QWidget
    start: Callable[[], None] | None = None
    stop: Callable[[], None] | None = None
    qss: str | None = None
    placeholder_reason: str | None = None


def placeholder(name: str, message: str) -> Section:
    label = QLabel(message)
    label.setObjectName("placeholder")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return Section(name, label, placeholder_reason=message)


def build_sections(active=None) -> list[Section]:
    """`active` is the app's one ActiveProject; PM (and QA after it) share
    it. None builds a private one -- a test, or a section on its own."""
    from seven_l1.sections.lotto import build_lotto_section
    from seven_l1.sections.pm import build_pm_section
    from seven_l1.sections.qa import build_qa_section
    from seven_l1.workspace.active import ActiveProject

    active = active if active is not None else ActiveProject()
    return [build_pm_section(active), build_qa_section(active), build_lotto_section()]
