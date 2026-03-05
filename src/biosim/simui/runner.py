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
    sim_time: Optional[float] = None
    sim_start: Optional[float] = None
    sim_end: Optional[float] = None
    sim_remaining: Optional[float] = None
    progress: Optional[float] = None
    progress_pct: Optional[float] = None


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
        data: Dict[str, Any] = {
            "running": st.running,
            "paused": st.paused,
            "started_at": _ts(st.started_at),
            "finished_at": _ts(st.finished_at),
            "tick_count": st.tick_count,
            "error": {"message": st.error} if st.error else None,
        }
        if st.sim_time is not None:
            data["sim_time"] = st.sim_time
        if st.sim_start is not None:
            data["sim_start"] = st.sim_start
        if st.sim_end is not None:
            data["sim_end"] = st.sim_end
        if st.sim_remaining is not None:
            data["sim_remaining"] = st.sim_remaining
        if st.progress is not None:
            data["progress"] = st.progress
        if st.progress_pct is not None:
            data["progress_pct"] = st.progress_pct
        return data

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
                with self._lock:
                    if ev == WorldEvent.TICK:
                        self._status.tick_count += 1
                    if ev == WorldEvent.PAUSED:
                        self._status.paused = True
                    elif ev == WorldEvent.RESUMED:
                        self._status.paused = False
                    _update_progress(self._status, payload)

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


def _coerce_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if out != out:  # NaN
        return None
    return out


def _update_progress(status: RunStatus, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    sim_time = _coerce_float(payload.get("t"))
    sim_start = _coerce_float(payload.get("start"))
    sim_end = _coerce_float(payload.get("end"))
    sim_remaining = _coerce_float(payload.get("remaining"))
    progress = _coerce_float(payload.get("progress"))
    progress_pct = _coerce_float(payload.get("progress_pct"))
    if sim_time is not None:
        status.sim_time = sim_time
    if sim_start is not None:
        status.sim_start = sim_start
    if sim_end is not None:
        status.sim_end = sim_end
    if sim_remaining is not None:
        status.sim_remaining = sim_remaining
    if progress is not None:
        status.progress = progress
    if progress_pct is not None:
        status.progress_pct = progress_pct


def _ts(t: Optional[float]) -> Optional[str]:
    if t is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
