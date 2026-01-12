# Contract: SimUI HTTP API

Status: Draft (living)
Last updated: 2026-01-12

Base path:
- mounted under `/ui` by default; API lives under `/ui/api/*`.

## Versioning

- `GET /api/spec` returns a `version` field (string).
- Backward-compatible additions are allowed within a major version.

## Endpoints

### `GET /api/spec`
Returns UI spec:
- `version: str`
- `title: str`
- `controls: list[controlSpec]`
- `outputs: list[outputSpec]`
- `modules: list[str]`

### `POST /api/run`
Request body (minimum):
- `steps: int` (>0)
- `dt: number`
Optional:
- additional run params (to be formalized; avoid private solver mutation)

Responses:
- `202` accepted (run started)
- `409` conflict if already running
- `400` for validation errors

### `GET /api/status`
Returns:
- `running: bool`
- `paused: bool`
- `started_at: str | null`
- `finished_at: str | null`
- `step_count: int`
- `error: { message: str } | null`

### `GET /api/events?since_id=<int>&limit=<int>`
Returns:
- `events: list[{ id:int, ts:str, event:str, payload:object }]`
- `next_since_id: int`

Rules:
- `limit` is capped (server-defined).
- events must be in chronological order; client can reverse for display.

### `GET /api/visuals`
Returns:
- list of `{ module: str, visuals: list[VisualSpec] }`

### `GET /api/snapshot`
Returns:
- `status: ...`
- `visuals: ...`
- `events: ...` (typically “all since start” for quick UI boot)

### `POST /api/pause`
Returns `{ ok: bool, reason?: str }`

### `POST /api/resume`
Returns `{ ok: bool, reason?: str }`

### `POST /api/reset`
Returns `{ ok: bool }`

## Error handling

- Errors should be returned as JSON with a clear message; 4xx for client issues, 5xx for server faults.
