import * as React from "react";
import { ChevronDown, ChevronRight, Loader2, Play, X } from "lucide-react";
import type { LabModelEntry, LocalLab, WorldIoPort } from "../types";
import { titleForModel } from "../lib/graph";
import { getModelParameterDescriptors, type ParameterDescriptor } from "../lib/parameters";

export type PreRunSubmit = {
  parameters: {
    initial_inputs: Record<string, unknown>;
    per_model: Record<string, Record<string, unknown>>;
  };
  simulation_config: {
    duration?: number;
    communication_step?: number;
    settle_steps?: number;
  };
};

export type PreRunModalProps = {
  lab: LocalLab;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (payload: PreRunSubmit) => void | Promise<void>;
};

function inferDefault(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function coerceNumberOrText(text: string): unknown {
  const trimmed = text.trim();
  if (trimmed.length === 0) return undefined;
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  const asNumber = Number(trimmed);
  if (Number.isFinite(asNumber) && trimmed.match(/^-?\d+(\.\d+)?(e[+-]?\d+)?$/i)) return asNumber;
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

function CollapsibleSection({
  title,
  count,
  defaultOpen = false,
  children,
}: {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <section className="modal-section">
      <button
        type="button"
        className="modal-section-toggle"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <h3>{title}</h3>
        {typeof count === "number" ? <span className="muted">{count}</span> : null}
      </button>
      {open ? <div className="modal-section-body">{children}</div> : null}
    </section>
  );
}

function getAcceptedUnits(entry: LabModelEntry, port: string): string[] {
  const inputs = entry.resolved_model?.io?.inputs;
  if (!Array.isArray(inputs)) return [];
  const spec = inputs.find((p) => p?.name === port);
  return Array.isArray(spec?.accepted_units) ? (spec!.accepted_units as string[]) : [];
}

function DescriptorInput({
  descriptor,
  value,
  onChange,
}: {
  descriptor: ParameterDescriptor;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="modal-param" title={descriptor.description}>
      <span>{descriptor.units ? `${descriptor.name} (${descriptor.units})` : descriptor.name}</span>
      <input
        type="number"
        step="any"
        min={descriptor.min}
        max={descriptor.max}
        value={value}
        placeholder={String(descriptor.value)}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export function PreRunModal({ lab, busy, onCancel, onSubmit }: PreRunModalProps) {
  const runtime = lab.manifest.runtime ?? {};
  const initialInputs = (runtime.initial_inputs as Record<string, unknown> | undefined) ?? {};
  const worldInputs: WorldIoPort[] = lab.manifest.io?.inputs ?? [];
  const models: LabModelEntry[] = lab.manifest.models ?? [];

  const [duration, setDuration] = React.useState<string>(() =>
    typeof runtime.duration === "number" ? String(runtime.duration) : "",
  );
  const [step, setStep] = React.useState<string>(() =>
    typeof runtime.communication_step === "number" ? String(runtime.communication_step) : "",
  );
  const [settleSteps, setSettleSteps] = React.useState<string>(() =>
    typeof runtime.settle_steps === "number" ? String(runtime.settle_steps) : "",
  );
  const [inputValues, setInputValues] = React.useState<Record<string, string>>(() => {
    const seed: Record<string, string> = {};
    for (const port of worldInputs) {
      seed[port.name] = inferDefault(initialInputs[port.name]);
    }
    return seed;
  });

  // For each model, sparse map of edited descriptor names → text value.
  const [paramEdits, setParamEdits] = React.useState<Record<string, Record<string, string>>>({});
  const [inputUnits, setInputUnits] = React.useState<Record<string, string>>({});
  const [error, setError] = React.useState<string | null>(null);

  // Resolve per-input metadata: subtitle (the maps_to ref) and accepted_units list. The unit
  // selector only renders when the model declares more than one accepted_unit for that port.
  const inputMeta = React.useMemo(() => {
    const map = new Map<string, { subtitle: string; units: string[] }>();
    for (const port of worldInputs) {
      const parsed = port.maps_to.split(".");
      const alias = parsed[0];
      const portName = parsed.slice(1).join(".");
      const model = models.find((m) => m.alias === alias);
      const units = model ? getAcceptedUnits(model, portName) : [];
      map.set(port.name, { subtitle: port.maps_to, units });
    }
    return map;
  }, [worldInputs, models]);

  function buildPayload(): PreRunSubmit | null {
    const initial: Record<string, unknown> = {};
    for (const port of worldInputs) {
      const raw = inputValues[port.name];
      const value = coerceNumberOrText(raw);
      if (value === undefined) continue;
      const unit = inputUnits[port.name];
      // If the user picked a unit, send the desktop-shaped {value, emitted_unit} envelope so
      // unit conversion happens server-side; otherwise send the bare value.
      initial[port.name] = unit ? { value, emitted_unit: unit } : value;
    }

    const perModel: Record<string, Record<string, unknown>> = {};
    for (const model of models) {
      const edits = paramEdits[model.alias] ?? {};
      const baseParams = (model.parameters as Record<string, unknown> | undefined) ?? {};
      const overlay: Record<string, unknown> = { ...baseParams };
      for (const [name, text] of Object.entries(edits)) {
        const trimmed = text.trim();
        if (trimmed.length === 0) continue;
        const n = Number(trimmed);
        overlay[name] = Number.isFinite(n) && /^-?\d+(\.\d+)?(e[+-]?\d+)?$/i.test(trimmed) ? n : trimmed;
      }
      if (Object.keys(overlay).length > 0) perModel[model.alias] = overlay;
    }

    const config: PreRunSubmit["simulation_config"] = {};
    if (duration.trim().length > 0) {
      const num = Number(duration);
      if (!Number.isFinite(num)) {
        setError("Duration must be a number.");
        return null;
      }
      config.duration = num;
    }
    if (step.trim().length > 0) {
      const num = Number(step);
      if (!Number.isFinite(num)) {
        setError("Communication step must be a number.");
        return null;
      }
      config.communication_step = num;
    }
    if (settleSteps.trim().length > 0) {
      const num = Number(settleSteps);
      if (!Number.isFinite(num) || !Number.isInteger(num) || num < 0) {
        setError("Settle steps must be a non-negative integer.");
        return null;
      }
      config.settle_steps = num;
    }

    return {
      parameters: { initial_inputs: initial, per_model: perModel },
      simulation_config: config,
    };
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const payload = buildPayload();
    if (payload) void onSubmit(payload);
  }

  function setParamEdit(alias: string, name: string, text: string) {
    setParamEdits((current) => ({
      ...current,
      [alias]: { ...(current[alias] ?? {}), [name]: text },
    }));
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <form
        className="modal pre-run-modal"
        onClick={(event) => event.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <div className="modal-header">
          <h2>Configure Run</h2>
          <button type="button" className="icon-button" onClick={onCancel} aria-label="Close">
            <X size={14} />
          </button>
        </div>
        <div className="modal-body">
          <CollapsibleSection title="Runtime" defaultOpen>
            <div className="modal-grid">
              <label className="modal-param">
                <span>Duration</span>
                <input value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="seconds" />
              </label>
              <label className="modal-param">
                <span>Communication step</span>
                <input
                  value={step}
                  onChange={(e) => setStep(e.target.value)}
                  placeholder="optional override"
                />
              </label>
              <label className="modal-param">
                <span>Settle steps</span>
                <input
                  value={settleSteps}
                  onChange={(e) => setSettleSteps(e.target.value)}
                  placeholder="0"
                />
              </label>
            </div>
          </CollapsibleSection>

          {worldInputs.length > 0 ? (
            <CollapsibleSection title="World Inputs" count={worldInputs.length}>
              <div className="modal-input-list">
                {worldInputs.map((port) => {
                  const meta = inputMeta.get(port.name);
                  const units = meta?.units ?? [];
                  const showUnitInline = units.length === 1;
                  const showUnitSelect = units.length > 1;
                  return (
                    <div key={port.name} className="modal-input-row">
                      <div className="modal-input-row-head">
                        <span className="modal-input-row-name">
                          {port.name}
                          {showUnitInline ? <span className="muted"> ({units[0]})</span> : null}
                        </span>
                        {showUnitSelect ? (
                          <select
                            className="modal-input-row-unit"
                            value={inputUnits[port.name] ?? ""}
                            aria-label={`${port.name} unit`}
                            onChange={(e) =>
                              setInputUnits((prev) => ({ ...prev, [port.name]: e.target.value }))
                            }
                          >
                            <option value="">Unit</option>
                            {units.map((unit) => (
                              <option key={unit} value={unit}>
                                {unit}
                              </option>
                            ))}
                          </select>
                        ) : null}
                      </div>
                      <span className="modal-input-row-subtitle">{port.maps_to}</span>
                      <input
                        className="modal-input-row-value"
                        value={inputValues[port.name] ?? ""}
                        placeholder="Leave blank to omit"
                        onChange={(e) =>
                          setInputValues((prev) => ({ ...prev, [port.name]: e.target.value }))
                        }
                      />
                    </div>
                  );
                })}
              </div>
            </CollapsibleSection>
          ) : null}

          {models.length > 0 ? (
            <CollapsibleSection title="Per-model parameters" count={models.length}>
              {models.map((model) => {
                const descriptors = getModelParameterDescriptors(model);
                const baseParams = (model.parameters as Record<string, unknown> | undefined) ?? {};
                return (
                  <ModelParametersBlock
                    key={model.alias}
                    title={titleForModel(model)}
                    alias={model.alias}
                    descriptors={descriptors}
                    baseParams={baseParams}
                    edits={paramEdits[model.alias] ?? {}}
                    onChange={(name, text) => setParamEdit(model.alias, name, text)}
                  />
                );
              })}
            </CollapsibleSection>
          ) : null}

          {error ? <div className="property-error">{error}</div> : null}
        </div>
        <div className="modal-footer">
          <button type="button" className="button" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="button primary" disabled={busy}>
            {busy ? <Loader2 size={13} className="spin" /> : <Play size={13} />}
            Start run
          </button>
        </div>
      </form>
    </div>
  );
}

function ModelParametersBlock({
  title,
  alias,
  descriptors,
  baseParams,
  edits,
  onChange,
}: {
  title: string;
  alias: string;
  descriptors: ParameterDescriptor[];
  baseParams: Record<string, unknown>;
  edits: Record<string, string>;
  onChange: (name: string, text: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <section className="modal-model-block">
      <button
        type="button"
        className="modal-section-toggle nested"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <strong>{title}</strong>
        <span className="muted">{alias}</span>
        <span className="muted">{descriptors.length} params</span>
      </button>
      {open ? (
        descriptors.length === 0 ? (
          <p className="muted small modal-param-empty">No parameters declared.</p>
        ) : (
          <div className="modal-grid">
            {descriptors.map((descriptor) => {
              const overrideValue = baseParams[descriptor.name];
              const text =
                edits[descriptor.name] !== undefined
                  ? edits[descriptor.name]
                  : typeof overrideValue === "number"
                    ? String(overrideValue)
                    : String(descriptor.value);
              return (
                <DescriptorInput
                  key={descriptor.name}
                  descriptor={descriptor}
                  value={text}
                  onChange={(next) => onChange(descriptor.name, next)}
                />
              );
            })}
          </div>
        )
      ) : null}
    </section>
  );
}
