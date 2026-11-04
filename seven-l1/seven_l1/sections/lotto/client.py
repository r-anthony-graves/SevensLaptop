"""Runs a PythonLotto simulation off the UI thread, cancellably.

A simulation is CPU-bound Python at roughly 200,000 draws a second, so the
10,000,000-draw cap holds a thread for about 50 s. It goes through
AsyncClient's relay like every other section's work: the worker never holds
the panel, so no QObject can be freed on the wrong thread.
"""

from __future__ import annotations

import logging
import threading

from seven_l1.asyncclient import AsyncClient

log = logging.getLogger(__name__)

# How long stop() waits for a cancelled run to end. The core checks for cancel
# every 5,000 draws -- about 25 ms at full speed -- so this is headroom.
STOP_WAIT_SECONDS = 2.0


class LottoClient(AsyncClient):
    """One simulation at a time: cancellable, and stoppable WITH a wait.

    AsyncClient.stop() only stops delivery; a worker already running keeps
    going. That is right for an HTTP call that ends on its own and wrong for
    a 50-second simulation. The app hides to the tray and quits from there,
    so a run that ignored stop() would outlive the window. stop() here
    cancels the run, then waits for it to end.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancel = threading.Event()
        self._idle = threading.Event()
        self._idle.set()

    @property
    def running(self) -> bool:
        return not self._idle.is_set()

    def simulate(self, engine, ticket, trials: int) -> str:
        """`trials` draws of `ticket`, on a worker thread.

        Progress arrives as line(rid, "<completed> <total>") every 5,000
        draws. The outcome arrives as done(rid, {"result": SimulationResult})
        or done(rid, {"error": message}); a LottoError's message is written
        for the user, so it is passed through as-is.
        """
        from pythonlotto import LottoError, simulate

        if self._stopped.is_set():
            # AsyncClient would start nothing, and a cleared _idle would then
            # never be set again: stop() would wait out its whole timeout.
            return ""
        self._cancel.clear()
        self._idle.clear()
        cancel, idle = self._cancel, self._idle

        def work(emit):
            try:
                result = simulate(
                    engine, ticket, trials,
                    progress=lambda done, total: emit(f"{done} {total}"),
                    should_cancel=cancel.is_set)
                return {"result": result}
            except LottoError as exc:
                return {"error": str(exc)}
            except Exception:
                # AsyncClient would turn this into a one-line dict and drop the
                # traceback. Log it here so the trace survives.
                log.exception("lotto simulation failed unexpectedly")
                return {"error": "The simulation failed unexpectedly -- see the desktop log."}
            finally:
                idle.set()

        return self.call_lines(work)

    def cancel(self) -> None:
        """Stop the running simulation at its next 5,000-draw boundary."""
        self._cancel.set()

    def stop(self) -> None:
        """Cancel, deliver nothing more, and wait for the worker to finish."""
        self._cancel.set()
        super().stop()
        if not self._idle.wait(STOP_WAIT_SECONDS):
            log.warning("lotto simulation still running %.1fs after stop", STOP_WAIT_SECONDS)
