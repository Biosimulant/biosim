export type SSEMessage = {
  type: 'snapshot' | 'event' | 'status' | 'tick' | 'heartbeat'
  data: unknown
}

export type SSESubscription = {
  close: () => void
}

export type Api = ReturnType<typeof makeApi>

export function makeApi(baseUrl: string) {
  const base = baseUrl.replace(/\/$/, '')
  async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${base}${path}`)
    if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
    return res.json() as Promise<T>
  }
  async function post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {})
    })
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
    return res.json() as Promise<T>
  }

  function subscribeSSE(onMessage: (msg: SSEMessage) => void, onError?: (err: Event) => void): SSESubscription {
    const eventSource = new EventSource(`${base}/api/stream`)
    eventSource.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as SSEMessage
        onMessage(msg)
      } catch (e) {
        console.error('Failed to parse SSE message:', e)
      }
    }
    eventSource.onerror = (err) => {
      if (onError) onError(err)
    }
    return {
      close: () => eventSource.close()
    }
  }

  return {
    spec: () => get('/api/spec'),
    status: () => get('/api/status'),
    state: () => get('/api/state'),
    events: (since_id?: number, limit = 200) => get(`/api/events?${new URLSearchParams({
      ...(since_id != null ? { since_id: String(since_id) } : {}),
      limit: String(limit)
    }).toString()}`),
    visuals: () => get('/api/visuals'),
    snapshot: () => get('/api/snapshot'),
    run: (steps: number, dt: number, extra?: Record<string, unknown>) => post('/api/run', { steps, dt, ...(extra || {}) }),
    pause: () => post('/api/pause', {}),
    resume: () => post('/api/resume', {}),
    reset: () => post('/api/reset', {}),
    subscribeSSE
  }
}
