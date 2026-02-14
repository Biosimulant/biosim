import { beforeEach, describe, expect, it, vi } from "vitest";

import { createSimuiApi } from "./api";

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
}

function okJson(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response;
}

function fail(status: number) {
  return {
    ok: false,
    status,
    json: vi.fn(),
  } as unknown as Response;
}

beforeEach(() => {
  vi.clearAllMocks();
  MockEventSource.instances = [];
  vi.stubGlobal("fetch", vi.fn());
  vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
});

describe("createSimuiApi", () => {
  it("hits spec/status/state endpoints", async () => {
    (fetch as any)
      .mockResolvedValueOnce(okJson({ version: "1" }))
      .mockResolvedValueOnce(okJson({ running: false }))
      .mockResolvedValueOnce(okJson({ ok: true }));

    const api = createSimuiApi("http://localhost:8080/");

    await api.spec();
    await api.status();
    await api.state();

    expect((fetch as any).mock.calls[0][0]).toBe("http://localhost:8080/api/spec");
    expect((fetch as any).mock.calls[1][0]).toBe("http://localhost:8080/api/status");
    expect((fetch as any).mock.calls[2][0]).toBe("http://localhost:8080/api/state");
  });

  it("builds events query params", async () => {
    (fetch as any)
      .mockResolvedValueOnce(okJson({ events: [], next_since_id: 1 }))
      .mockResolvedValueOnce(okJson({ events: [], next_since_id: 2 }));

    const api = createSimuiApi("http://localhost:8080");

    await api.events(undefined, 150);
    await api.events(33, 10);

    expect((fetch as any).mock.calls[0][0]).toBe("http://localhost:8080/api/events?limit=150");
    expect((fetch as any).mock.calls[1][0]).toBe("http://localhost:8080/api/events?since_id=33&limit=10");
  });

  it("runs pause/resume/reset and snapshot/visuals", async () => {
    (fetch as any)
      .mockResolvedValueOnce(okJson([{ module: "m", visuals: [] }]))
      .mockResolvedValueOnce(okJson({ status: { running: false }, visuals: [], events: [] }))
      .mockResolvedValueOnce(okJson({ ok: true }))
      .mockResolvedValueOnce(okJson({ ok: true }))
      .mockResolvedValueOnce(okJson({ ok: true }))
      .mockResolvedValueOnce(okJson({ ok: true }));

    const api = createSimuiApi("http://localhost:8080");

    await api.visuals();
    await api.snapshot();
    await api.run(12, 0.5, { seed: 1 });
    await api.pause();
    await api.resume();
    await api.reset();

    expect((fetch as any).mock.calls[2][1]).toMatchObject({ method: "POST" });
    expect((fetch as any).mock.calls[2][1].body).toBe(JSON.stringify({ duration: 12, tick_dt: 0.5, seed: 1 }));
  });

  it("exercises editor API endpoints", async () => {
    (fetch as any)
      .mockResolvedValueOnce(okJson({ modules: {}, categories: {} }))
      .mockResolvedValueOnce(okJson({ nodes: [], edges: [], meta: {} }))
      .mockResolvedValueOnce(okJson({ available: true, path: "a.yaml", graph: { nodes: [], edges: [], meta: {} } }))
      .mockResolvedValueOnce(okJson({ ok: true, path: "b.yaml" }))
      .mockResolvedValueOnce(okJson({ ok: true, path: "c.yaml" }))
      .mockResolvedValueOnce(okJson({ valid: true, errors: [] }))
      .mockResolvedValueOnce(okJson({ nodes: [], edges: [], meta: {} }))
      .mockResolvedValueOnce(okJson({ yaml: "x: 1" }))
      .mockResolvedValueOnce(okJson({ nodes: [], edges: [], meta: {} }))
      .mockResolvedValueOnce(okJson([{ name: "a.yaml", path: "/", is_dir: false }]))
      .mockResolvedValueOnce(okJson([{ name: "b.yaml", path: "/", is_dir: false }]));

    const api = createSimuiApi("http://localhost:8080");
    const graph = { nodes: [], edges: [], meta: {} } as any;

    await api.editor!.getModules();
    await api.editor!.getConfig("foo/bar.yaml");
    await api.editor!.getCurrent();
    await api.editor!.saveConfig("out.yaml", graph);
    await api.editor!.applyConfig(graph, "apply.yaml");
    await api.editor!.validate(graph);
    await api.editor!.layout(graph);
    await api.editor!.toYaml(graph);
    await api.editor!.fromYaml("x: 1");
    await api.editor!.listFiles("/tmp");
    await api.editor!.listFiles();

    expect((fetch as any).mock.calls[1][0]).toContain("path=foo%2Fbar.yaml");
    expect((fetch as any).mock.calls[3][1].method).toBe("PUT");
    expect((fetch as any).mock.calls[9][0]).toContain("?path=%2Ftmp");
    expect((fetch as any).mock.calls[10][0]).toBe("http://localhost:8080/api/editor/files");
  });

  it("handles GET/POST/PUT errors", async () => {
    (fetch as any)
      .mockResolvedValueOnce(fail(500))
      .mockResolvedValueOnce(fail(400))
      .mockResolvedValueOnce(fail(422));

    const api = createSimuiApi("http://localhost:8080");

    await expect(api.spec()).rejects.toThrow("GET /api/spec failed: 500");
    await expect(api.run(1)).rejects.toThrow("POST /api/run failed: 400");
    await expect(api.editor!.saveConfig("x", { nodes: [], edges: [], meta: {} } as any)).rejects.toThrow(
      "PUT /api/editor/config failed: 422",
    );
  });

  it("subscribes to SSE and handles parse/errors", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const onMessage = vi.fn();
    const onError = vi.fn();
    const api = createSimuiApi("http://localhost:8080");

    const sub = api.subscribeSSE(onMessage, onError);
    const source = MockEventSource.instances[0];

    source.onmessage?.({ data: JSON.stringify({ type: "heartbeat", data: { ok: true } }) });
    source.onmessage?.({ data: "not-json" });
    source.onerror?.(new Event("error"));
    sub.close();

    expect(source.url).toBe("http://localhost:8080/api/stream");
    expect(onMessage).toHaveBeenCalledWith({ type: "heartbeat", data: { ok: true } });
    expect(onError).toHaveBeenCalled();
    expect(errorSpy).toHaveBeenCalled();
    expect(source.close).toHaveBeenCalled();

    errorSpy.mockRestore();
  });
});
