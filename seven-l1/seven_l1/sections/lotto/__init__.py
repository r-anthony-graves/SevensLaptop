"""Lotto: exact lottery odds and Monte Carlo draws for any "pick K of N, plus
B of M" game, over the pythonlotto core library -- natively, in place of
PythonLotto's Textual UI, which cannot render inside a Qt window."""

from __future__ import annotations


def build_lotto_section():
    from seven_l1.sections import Section
    from seven_l1.sections.lotto.panel import LottoPanel

    panel = LottoPanel()
    return Section("Lotto", panel, stop=panel.stop)
