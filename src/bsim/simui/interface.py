from __future__ import annotations
import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Deque, Dict, List, Optional, Sequence, Set
import logging

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..world import BioWorld, WorldEvent
from .runner import SimulationManager
from .editor_api import build_editor_router

logger = logging.getLogger(__name__)


# ----------------------------- Components ---------------------------------


@dataclass
class Number:
    name: str
    default: float
    label: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None


@dataclass
class Button:
    label: str = "Run"


@dataclass
class EventLog:
    limit: int = 200


@dataclass
class VisualsPanel:
    refresh: str = "auto"  # "auto" | "manual"
    interval_ms: int = 500


# ------------------------------- Interface --------------------------------


class Interface:
    """Python-first UI interface that can be launched or mounted.

    - Collects events from the BioWorld using a listener.
    - Exposes REST endpoints for run control, status, events, and visuals.
    - Serves a static React SPA (prebuilt) to render controls/outputs.
    """

    def __init__(
        self,
        world: BioWorld,
        *,
        title: str = "BioSim UI",
        description: str | None = None,
        controls: Sequence[Any] | None = None,
        outputs: Sequence[Any] | None = None,
        mount_path: str = "/ui",
        config_path: str | Path | None = None,
    ) -> None:
        self._world = world
        self._title = title
        self._description = description
        self._config_path: Path | None = Path(config_path) if config_path else None
        # Base controls
        base_controls = [Number("duration", 10.0), Number("tick_dt", 0.1), Button("Run")]
        self._controls = list(controls or base_controls)
        self._outputs = list(outputs or [EventLog(), VisualsPanel()])
        self._mount_path = mount_path.rstrip("/") or "/ui"

        # Event buffer (timestamped + monotonic id). Bounded to avoid unbounded memory growth.
        event_limit = 200
        for out in self._outputs:
            if isinstance(out, EventLog):
                event_limit = max(1, int(out.limit))
                break
        self._event_limit = event_limit
        self._events: Deque[Dict[str, Any]] = deque(maxlen=self._event_limit)
        self._events_lock = threading.Lock()
        self._event_seq: int = 0

        # Register listener
        self._world.on(self._listener)

        # Runtime snapshot fields
        self._last_step = None

        # Runner (status is polled by frontend)
        self._runner = SimulationManager(self._world)

        # SSE subscribers: each subscriber gets a Queue for pushed events
        self._sse_subscribers: Set[Queue[Dict[str, Any]]] = set()
        self._sse_lock = threading.Lock()

        # Routing / app (must be inside __init__)
        self._router = self._build_router()

    # ---- Public API ------------------------------------------------------
    def launch(self, host: str = "127.0.0.1", port: int = 7860, open_browser: bool = False) -> None:
        """Start a managed uvicorn server to serve the UI.

        Note: blocking call. Intended for development use.
        """
        import uvicorn
        app = FastAPI()
        self.mount(app, self._mount_path)
        if open_browser:
            try:
                import webbrowser

                webbrowser.open(f"http://{host}:{port}{self._mount_path}/")
            except Exception:
                pass
        uvicorn.run(app, host=host, port=port)

    def mount(self, app: FastAPI, path: Optional[str] = None) -> None:
        mount_at = (path or self._mount_path).rstrip("/")
        # Static files: serve prebuilt React assets
        static_dir = Path(__file__).with_suffix("").parent / "static"
        app_js = static_dir / "app.js"
        if not app_js.exists():
            raise RuntimeError(
                f"SimUI static bundle missing at {app_js}. Install the package with UI assets or build the frontend."
            )
        app.mount(f"{mount_at}/static", StaticFiles(directory=str(static_dir)), name="bsim_simui_static")
        # API + index
        app.include_router(self._router, prefix=mount_at)

    def close(self) -> None:
        try:
            self._world.off(self._listener)
        except Exception:
            pass

    # ---- Internal: event listener and buffers ---------------------------
    def _listener(self, event: WorldEvent, payload: Dict[str, Any]) -> None:
        self._event_seq += 1
        event_name = event.value if hasattr(event, "value") else str(event)
        record = {
            "id": self._event_seq,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event_name,
            "payload": payload,
        }
        with self._events_lock:
            self._events.append(record)
            if event == WorldEvent.TICK:
                self._last_step = payload

        # Push to SSE subscribers
        if event == WorldEvent.TICK:
            # On STEP, send a tick with status, visuals, and the event
            self._broadcast_sse({
                "type": "tick",
                "data": {
                    "status": self._runner.status(),
                    "visuals": self._collect_visuals_safe(),
                    "event": record,
                },
            })
        else:
            # Other events just push the event record
            self._broadcast_sse({
                "type": "event",
                "data": record,
            })

    def _collect_visuals_safe(self) -> List[Dict[str, Any]]:
        """Collect visuals with error handling."""
        try:
            collected = self._world.collect_visuals()
            return [
                {
                    "module": entry.get("module"),
                    "visuals": [
                        {
                            "render": v["render"],
                            "data": v["data"],
                            **({"description": v["description"]} if "description" in v else {}),
                        }
                        for v in entry.get("visuals", [])
                    ],
                }
                for entry in collected
            ]
        except Exception:
            return []

    def _events_since(self, since_id: Optional[int], limit: int) -> Dict[str, Any]:
        with self._events_lock:
            items = list(self._events)
        if since_id is not None:
            items = [e for e in items if int(e.get("id", 0)) > int(since_id)]
        if limit > 0:
            items = items[-limit:]
        next_since_id = int(items[-1]["id"]) if items else (int(since_id) if since_id is not None else 0)
        return {"events": items, "next_since_id": next_since_id}

    def _broadcast_sse(self, message: Dict[str, Any]) -> None:
        """Push a message to all SSE subscribers."""
        with self._sse_lock:
            for q in list(self._sse_subscribers):
                try:
                    q.put_nowait(message)
                except Exception:
                    pass  # Queue full or closed

    def _subscribe_sse(self) -> Queue[Dict[str, Any]]:
        """Create and register a new SSE subscriber queue."""
        q: Queue[Dict[str, Any]] = Queue(maxsize=100)
        with self._sse_lock:
            self._sse_subscribers.add(q)
        return q

    def _unsubscribe_sse(self, q: Queue[Dict[str, Any]]) -> None:
        """Remove an SSE subscriber queue."""
        with self._sse_lock:
            self._sse_subscribers.discard(q)

    # ---- Internal: API router -------------------------------------------
    def _build_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/", response_class=HTMLResponse)
        def index() -> str:
            # Minimal HTML that loads the compiled frontend bundle.
            static_dir = Path(__file__).with_suffix("").parent / "static"
            app_css = ("<link rel='stylesheet' href='static/app.css'>" if (static_dir / "app.css").exists() else "")
            return (
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{self._title}</title>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                f"{app_css}"
                "</head><body>"
                "<div id='app'></div>"
                "<script>window.__BSIM_UI__ = { mountPath: location.pathname.replace(/\\/$/, '') };</script>"
                "<script type='module' src='static/app.js'></script>"
                "</body></html>"
            )

        @router.get("/api/spec")
        def spec() -> Dict[str, Any]:
            try:
                modules = list(self._world.module_names)  # type: ignore[attr-defined]
            except Exception:
                modules = []
            controls = [self._ctrl_to_spec(c) for c in self._controls]
            controls = [c for c in controls if c is not None]
            outputs = [self._out_to_spec(o) for o in self._outputs]
            outputs = [o for o in outputs if o is not None]
            return {
                "version": "2",
                "title": self._title,
                "description": self._description,
                "controls": controls,
                "outputs": outputs,
                "modules": modules,
            }

        @router.post("/api/run")
        def run(params: Dict[str, Any]) -> JSONResponse:
            duration = params.get("duration")
            tick_dt = params.get("tick_dt")
            try:
                duration_f = float(duration)
            except Exception:
                raise HTTPException(status_code=400, detail="'duration' must be a number")
            if duration_f <= 0:
                raise HTTPException(status_code=400, detail="'duration' must be positive")
            try:
                tick_f = float(tick_dt) if tick_dt is not None else None
            except Exception:
                raise HTTPException(status_code=400, detail="'tick_dt' must be a number")
            if tick_f is not None and tick_f <= 0:
                raise HTTPException(status_code=400, detail="'tick_dt' must be positive")

            def _on_start() -> None:
                # Clear backend event buffers for a fresh run view (before the worker thread starts emitting).
                with self._events_lock:
                    self._events.clear()
                    self._event_seq = 0
                self._last_step = None

            started = self._runner.start_run(duration=duration_f, tick_dt=tick_f, on_start=_on_start)
            if not started:
                return JSONResponse({"ok": False, "reason": "already_running"}, status_code=409)
            return JSONResponse({"ok": True}, status_code=202)

        @router.get("/api/status")
        def status() -> Dict[str, Any]:
            return self._runner.status()

        @router.get("/api/state")
        def state() -> Dict[str, Any]:
            return {
                "status": self._runner.status(),
                "last_step": self._last_step,
                "modules": list(self._world.module_names),  # type: ignore[attr-defined]
            }

        @router.post("/api/pause")
        def pause() -> Dict[str, Any]:
            st = self._runner.status()
            if not st.get("running"):
                return {"ok": False, "reason": "not_running"}
            if st.get("paused"):
                return {"ok": False, "reason": "already_paused"}
            self._runner.pause()
            return {"ok": True}

        @router.post("/api/resume")
        def resume() -> Dict[str, Any]:
            st = self._runner.status()
            if not st.get("running"):
                return {"ok": False, "reason": "not_running"}
            if not st.get("paused"):
                return {"ok": False, "reason": "not_paused"}
            self._runner.resume()
            return {"ok": True}

        @router.get("/api/events")
        def events(since_id: Optional[int] = None, limit: int = 200) -> Dict[str, Any]:
            limit = max(0, min(self._event_limit, int(limit)))
            return self._events_since(since_id, limit)

        @router.get("/api/visuals")
        def visuals() -> List[Dict[str, Any]]:
            collected = self._world.collect_visuals()
            # ensure visuals are normalized JSON-friendly
            out: List[Dict[str, Any]] = []
            for entry in collected:
                out.append({
                    "module": entry.get("module"),
                    "visuals": [
                        {
                            "render": v["render"],
                            "data": v["data"],
                            **({"description": v["description"]} if "description" in v else {}),
                        }
                        for v in entry.get("visuals", [])
                    ],
                })
            return out

        @router.get("/api/snapshot")
        def snapshot() -> Dict[str, Any]:
            # Full snapshot: status, all visuals, and all events since start
            st = self._runner.status()
            vis = visuals()
            ev = self._events_since(None, 0)  # limit=0 => no limit
            return {"status": st, "visuals": vis, "events": ev.get("events", [])}

        @router.get("/api/stream")
        async def stream(request: Request) -> StreamingResponse:
            """SSE endpoint for real-time event streaming."""
            queue = self._subscribe_sse()

            async def event_generator():
                try:
                    # Send initial snapshot
                    st = self._runner.status()
                    vis_data = visuals()
                    ev = self._events_since(None, 0)
                    init_msg = {
                        "type": "snapshot",
                        "data": {"status": st, "visuals": vis_data, "events": ev.get("events", [])},
                    }
                    yield f"data: {json.dumps(init_msg)}\n\n"

                    # Event loop with adaptive heartbeat
                    last_activity = time.time()
                    while True:
                        if await request.is_disconnected():
                            break

                        # Drain all available messages
                        sent_any = False
                        while True:
                            try:
                                msg = queue.get_nowait()
                                yield f"data: {json.dumps(msg)}\n\n"
                                sent_any = True
                                last_activity = time.time()
                            except Empty:
                                break

                        if sent_any:
                            # Brief yield to allow more messages to accumulate
                            await asyncio.sleep(0.05)
                        else:
                            # No messages - send heartbeat if needed
                            now = time.time()
                            if now - last_activity > 2.0:
                                # Send heartbeat every 2s when idle
                                yield f"data: {json.dumps({'type': 'heartbeat', 'data': self._runner.status()})}\n\n"
                                last_activity = now
                            await asyncio.sleep(0.1)
                finally:
                    self._unsubscribe_sse(queue)

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        @router.post("/api/reset")
        def reset() -> Dict[str, Any]:
            # Attempt cooperative stop if running, then reset and clear buffers
            try:
                self._runner.reset()
            except Exception:
                pass
            with self._events_lock:
                self._events.clear()
                self._event_seq = 0
            self._last_step = None
            return {"ok": True}

        # Include the config editor API router
        editor_router = build_editor_router(
            get_config_path=lambda: self._config_path,
            get_world=lambda: self._world,
            reload_world=self._reload_world,
        )
        router.include_router(editor_router, prefix="/api")

        return router

    # ---- Config reload ----------------------------------------------------
    def _reload_world(self, new_config_path: Path | None = None) -> bool:
        """Reload the world from config file.

        This clears existing modules and rewires from the config.
        Returns True on success, False on failure.
        """
        import biosim

        config_path = new_config_path or self._config_path
        if not config_path or not config_path.exists():
            logger.error("Cannot reload: no config path available")
            return False

        try:
            # Stop any running simulation
            self._runner.reset()

            # Clear existing modules from the world
            for module in list(self._world._biomodule_listeners.keys()):
                self._world.remove_biomodule(module)

            # Clear signal routes
            self._world._signal_routes.clear()

            # Reload wiring from config
            biosim.load_wiring(self._world, config_path)

            # Update stored config path
            self._config_path = config_path

            # Clear event buffers
            with self._events_lock:
                self._events.clear()
                self._event_seq = 0
            self._last_step = None

            logger.info(f"Reloaded world from {config_path}")
            return True
        except Exception:
            logger.exception(f"Failed to reload world from {config_path}")
            return False

    # ---- Helpers ---------------------------------------------------------
    @staticmethod
    def _ctrl_to_spec(ctrl: Any) -> Optional[Dict[str, Any]]:
        if isinstance(ctrl, Number):
            return {
                "type": "number",
                "name": ctrl.name,
                "label": ctrl.label or ctrl.name,
                "default": ctrl.default,
                "min": ctrl.minimum,
                "max": ctrl.maximum,
                "step": ctrl.step,
            }
        if isinstance(ctrl, Button):
            return {"type": "button", "label": ctrl.label}
        # Unknown control types are ignored (no fallback)
        return None

    @staticmethod
    def _out_to_spec(out: Any) -> Optional[Dict[str, Any]]:
        if isinstance(out, EventLog):
            return {"type": "event_log", "limit": out.limit}
        if isinstance(out, VisualsPanel):
            return {"type": "visuals", "refresh": out.refresh, "interval_ms": out.interval_ms}
        # Unknown outputs are ignored (no fallback)
        return None

    # (SSE helpers removed)
