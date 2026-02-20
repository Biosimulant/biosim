from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class RunStatus:
    running: bool = False
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    tick_count: int = 0
    error: Optional[str] = None
    paused: bool = False


class SimulationManager:
    """Runs world.run in a background thread and tracks status."""

    def __init__(self, world: "BioWorld") -> None:
        self._world = world
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._status = RunStatus()
        self._stop_requested = False

    # External API ---------------------------------------------------------
    def start_run(
        self,
        *,
        duration: float,
        tick_dt: Optional[float],
        on_start: Optional[Callable[[], None]] = None,
    ) -> bool:
        """Attempt to start a background run. Returns False if already running."""
        with self._lock:
            if self._status.running:
                return False
            if on_start is not None:
                on_start()
            self._status = RunStatus(running=True, started_at=time.time(), tick_count=0, error=None)
            self._stop_requested = False
            self._thread = threading.Thread(target=self._worker, args=(duration, tick_dt), daemon=True)
            self._thread.start()
            return True

    def status(self) -> Dict[str, Any]:
        st = self._status
        return {
            "running": st.running,
            "paused": st.paused,
            "started_at": _ts(st.started_at),
            "finished_at": _ts(st.finished_at),
            "tick_count": st.tick_count,
            "error": {"message": st.error} if st.error else None,
        }

    def join(self, timeout: Optional[float] = None) -> None:
        t = self._thread
        if t is not None:
            t.join(timeout=timeout)

    def request_stop(self) -> None:
        try:
            self._world.request_stop()  # type: ignore[attr-defined]
        except Exception:
            pass
        self._stop_requested = True

    def pause(self) -> None:
        if not self._status.running:
            return
        try:
            self._world.request_pause()  # type: ignore[attr-defined]
        except Exception:
            pass
        with self._lock:
            self._status.paused = True

    def resume(self) -> None:
        try:
            self._world.request_resume()  # type: ignore[attr-defined]
        except Exception:
            pass
        with self._lock:
            self._status.paused = False

    def reset(self) -> None:
        """Reset internal status if not running."""
        if self._status.running:
            self.request_stop()
            t = self._thread
            if t is not None:
                t.join(timeout=2.0)
        with self._lock:
            if not self._status.running:
                self._status = RunStatus()

    # Internal -------------------------------------------------------------
    def _worker(self, duration: float, tick_dt: Optional[float]) -> None:
        try:
            from biosim.world import WorldEvent  # lazy to avoid circulars

            def _counter(ev, payload):
                if ev == WorldEvent.TICK:
                    self._status.tick_count += 1

            self._world.on(_counter)
            try:
                self._world.run(duration=duration, tick_dt=tick_dt)
            finally:
                self._world.off(_counter)
        except Exception as exc:  # pragma: no cover
            with self._lock:
                self._status.error = str(exc)
                self._status.running = False
                self._status.finished_at = time.time()
            return
        with self._lock:
            self._status.running = False
            self._status.finished_at = time.time()



def _ts(t: Optional[float]) -> Optional[str]:
    if t is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
