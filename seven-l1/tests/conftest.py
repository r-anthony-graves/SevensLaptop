"""Shared test setup. Offscreen Qt, like D:\\tradinglocal's own
tests/command_center/conftest.py.

NO __init__.py in this directory, and --import-mode=importlib in pytest.ini:
importing the trader puts D:\\tradinglocal on sys.path, and that repo owns
the top-level names `agent`, `engine` and `tests`.
"""

import os
import pathlib
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# --------------------------------------------------------- the ade-ai mirror
#
# A few tests here pin this app against its source of truth in Ade OS: PM's
# slug against adeos/records/pmi.py, QA's catalogue against the web's
# qaNav.ts. They hardcoded C:\Users\ray_g\ade-ai, which is not where this
# checkout is, so test_pm_logic skipped and test_qa quietly ran HALF of
# itself behind a bare `if WEB.exists()` -- reported as a pass. Both were
# proving nothing (found 2026-11-04 during the Seven-L1 rename).

_ADE_AI_CANDIDATES = (
    pathlib.Path.home() / "Projects" / "ade-ai",
    pathlib.Path.home() / "ade-ai",
    pathlib.Path(r"C:\Users\ray_g\ade-ai"),
    pathlib.Path(r"C:\Users\ray_g\Projects\ade-ai"),
)


def ade_ai_root():
    """The ade-ai checkout this app mirrors, or None if there isn't one.

    SEVEN_L1_ADE_AI wins, so a machine that keeps it anywhere else needs no
    edit here. A directory only counts when `adeos/` is in it: an empty or
    half-deleted folder of the right name must not pass for a checkout.
    """
    override = os.environ.get("SEVEN_L1_ADE_AI")
    candidates = (pathlib.Path(override),) if override else _ADE_AI_CANDIDATES
    for root in candidates:
        try:
            if (root / "adeos").is_dir():
                return root
        except OSError:
            continue
    return None


def _ade_ai_file(relpath: str) -> pathlib.Path:
    """A file inside the ade-ai checkout, for a cross-repo test.

    No checkout at all -> skip: a fresh clone of this repo alone is a real
    and supported case. A checkout that IS here but no longer holds the
    file -> FAIL, loudly. That second case is the one worth catching: it
    means the thing this test mirrors was moved or renamed, which is
    exactly when a silent skip would hide the drift.
    """
    root = ade_ai_root()
    if root is None:
        pytest.skip("no ade-ai checkout here (set SEVEN_L1_ADE_AI to point at one)")
    path = root / relpath
    if not path.exists():
        raise AssertionError(
            f"ade-ai is at {root}, but {relpath} is not in it. This test mirrors "
            f"that file; if it moved or was renamed, follow it here rather than "
            f"letting this test go quiet."
        )
    return path


@pytest.fixture
def ade_ai_file():
    """`ade_ai_file("adeos/records/pmi.py")` -> Path, or an out-loud skip.

    A fixture, not an import: pytest.ini runs --import-mode=importlib, which
    does NOT put this directory on sys.path, so `from conftest import ...`
    is not reliably available to a test module.
    """
    return _ade_ai_file


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def pump(qapp):
    """Process Qt events until predicate() is true or timeout passes.
    Results from worker threads arrive as queued signals, which only land
    while events are being processed."""

    def _pump(predicate, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            qapp.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        qapp.processEvents()
        return bool(predicate())

    return _pump





@pytest.fixture(autouse=True)
def _deferred_deletes_run_in_their_own_test(request):
    """Run each test's deleteLater()s at ITS teardown. Left queued, they ran
    at the next test that happened to pump events -- the orb's voice tests,
    last in the order -- and a crash in a deletion named the wrong test
    (2026-09-18: a SingleInstance socket deleted twice aborted the suite
    inside test_voice_controller)."""
    yield
    if "qapp" in request.fixturenames:
        from PySide6.QtCore import QCoreApplication, QEvent

        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)



@pytest.fixture(autouse=True)
def _fresh_filling_registry():
    """The "being written" registry is process-wide by design (one answer
    for the app); a test's unfinished flow must not leave marks for the
    next test to trip over."""
    yield
    from seven_l1.workspace import filling as registry

    registry._FILLING = None
