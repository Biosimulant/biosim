import { describe, expect, it } from "vitest";

import { resolveConfig } from "./config";

describe("resolveConfig", () => {
  it("uses mount path from window if present", () => {
    (window as any).__BSIM_UI__ = { mountPath: "/sim" };
    expect(resolveConfig()).toEqual({ baseUrl: "/sim" });
  });

  it("defaults baseUrl to empty string", () => {
    delete (window as any).__BSIM_UI__;
    expect(resolveConfig()).toEqual({ baseUrl: "" });
  });
});
