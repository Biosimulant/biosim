import type { LabModelEntry } from "../types";

export type ParameterDescriptor = {
  name: string;
  value: number;
  min?: number;
  max?: number;
  units?: string;
  description?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function descriptorsFromArray(value: unknown): ParameterDescriptor[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!isRecord(entry) || typeof entry.name !== "string") return [];
    const raw = entry.value ?? entry.default;
    if (typeof raw !== "number" || !Number.isFinite(raw)) return [];
    return [
      {
        name: entry.name,
        value: raw,
        min: typeof entry.min === "number" ? entry.min : undefined,
        max: typeof entry.max === "number" ? entry.max : undefined,
        units: typeof entry.units === "string" ? entry.units : undefined,
        description: typeof entry.description === "string" ? entry.description : undefined,
      },
    ];
  });
}

/**
 * Mirror of the desktop's `getNodeParameterDescriptors`: prefer `resolved_model.biosim.init_kwargs`
 * (numeric defaults), then fall back to typed descriptor arrays in the resolved manifest, finally
 * to the lab-level overrides on the entry itself.
 */
export function getModelParameterDescriptors(entry: LabModelEntry): ParameterDescriptor[] {
  const initKwargs = entry.resolved_model?.biosim?.init_kwargs;
  if (initKwargs && typeof initKwargs === "object") {
    const out: ParameterDescriptor[] = [];
    for (const [name, value] of Object.entries(initKwargs)) {
      if (typeof value === "number" && Number.isFinite(value)) out.push({ name, value });
    }
    if (out.length > 0) return enrichWithIoUnits(out, entry);
  }

  const top = descriptorsFromArray(entry.resolved_model?.manifest?.parameters);
  if (top.length > 0) return enrichWithIoUnits(top, entry);

  const biosim = descriptorsFromArray(entry.resolved_model?.biosim?.parameters);
  if (biosim.length > 0) return enrichWithIoUnits(biosim, entry);

  // Fall back to whatever override values the lab has stored.
  if (entry.parameters && Object.keys(entry.parameters).length > 0) {
    const out: ParameterDescriptor[] = [];
    for (const [name, value] of Object.entries(entry.parameters)) {
      if (typeof value === "number" && Number.isFinite(value)) out.push({ name, value });
    }
    return enrichWithIoUnits(out, entry);
  }

  return [];
}

/** Add units/descriptions from `resolved_model.io.inputs` to descriptors of the same name. */
function enrichWithIoUnits(descriptors: ParameterDescriptor[], entry: LabModelEntry): ParameterDescriptor[] {
  const inputs = entry.resolved_model?.io?.inputs;
  if (!Array.isArray(inputs)) return descriptors;
  const byName = new Map<string, { units?: string; description?: string }>();
  for (const port of inputs) {
    if (!port?.name) continue;
    byName.set(port.name, {
      units: Array.isArray(port.accepted_units) && typeof port.accepted_units[0] === "string"
        ? port.accepted_units[0]
        : undefined,
      description: port.description,
    });
  }
  return descriptors.map((d) => {
    const enrich = byName.get(d.name);
    if (!enrich) return d;
    return { ...d, units: d.units ?? enrich.units, description: d.description ?? enrich.description };
  });
}
