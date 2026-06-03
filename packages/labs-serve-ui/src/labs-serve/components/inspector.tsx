import * as React from "react";
import { ArrowRight, Cable, ChevronRight, Plus, Save, Trash2, X } from "lucide-react";
import type {
  LabChildEntry,
  LabModelEntry,
  LocalLab,
  Selection,
  WiringEntry,
  WorldIoPort,
} from "../types";
import { getLabPorts, getModelPorts, titleForLab, titleForModel } from "../lib/graph";
import { getModelParameterDescriptors, type ParameterDescriptor } from "../lib/parameters";

export type InspectorProps = {
  lab: LocalLab | null;
  selection: Selection;
  onClose: () => void;
  onSaveModel?: (
    alias: string,
    body: { parameters?: Record<string, unknown> },
  ) => Promise<void>;
  onSaveWorld?: (body: {
    inputs?: WorldIoPort[];
    outputs?: WorldIoPort[];
    runtime?: Record<string, unknown>;
    wiring?: WiringEntry[];
  }) => Promise<void>;
};

function PropertySection({
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
    <section className="property-collapse">
      <button
        type="button"
        className="property-collapse-header"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <ChevronRight size={12} className={`property-chevron ${open ? "open" : ""}`} />
        <span>{title}</span>
        {typeof count === "number" ? <span className="muted">{count}</span> : null}
      </button>
      {open ? <div className="property-collapse-body">{children}</div> : null}
    </section>
  );
}

function valueToString(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function stringToValue(text: string, original: unknown): unknown {
  const trimmed = text.trim();
  if (trimmed.length === 0) return "";
  // Preserve type-fidelity with the original where possible.
  if (typeof original === "number") {
    const n = Number(trimmed);
    return Number.isFinite(n) ? n : trimmed;
  }
  if (typeof original === "boolean") {
    if (trimmed === "true") return true;
    if (trimmed === "false") return false;
    return trimmed;
  }
  if (typeof original === "string") return trimmed;
  // Objects, arrays, null — try JSON.
  try {
    return JSON.parse(trimmed);
  } catch {
    if (trimmed === "true") return true;
    if (trimmed === "false") return false;
    const n = Number(trimmed);
    if (Number.isFinite(n) && /^-?\d+(\.\d+)?(e[+-]?\d+)?$/i.test(trimmed)) return n;
    return trimmed;
  }
}

function recordsEqual(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  const aKeys = Object.keys(a).sort();
  const bKeys = Object.keys(b).sort();
  if (aKeys.length !== bKeys.length) return false;
  if (aKeys.some((k, i) => k !== bKeys[i])) return false;
  return aKeys.every((k) => JSON.stringify(a[k]) === JSON.stringify(b[k]));
}

function ParameterField({
  name,
  original,
  value,
  onChange,
  onRemove,
}: {
  name: string;
  original: unknown;
  value: string;
  onChange: (next: string) => void;
  onRemove?: () => void;
}) {
  const isComplex = typeof original === "object" && original !== null;
  return (
    <div className="param-field">
      <div className="param-field-label">
        <span title={name}>{name}</span>
        {onRemove ? (
          <button type="button" className="icon-button tiny" title="Remove" onClick={onRemove}>
            <Trash2 size={11} />
          </button>
        ) : null}
      </div>
      {isComplex ? (
        <textarea
          className="param-field-textarea"
          rows={3}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
        />
      ) : (
        <input
          className="param-field-input"
          type={typeof original === "number" ? "number" : "text"}
          value={value}
          step={typeof original === "number" ? "any" : undefined}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
        />
      )}
    </div>
  );
}

function PortListBody({ ports }: { ports: string[] }) {
  if (ports.length === 0) return <p className="muted small">none</p>;
  return (
    <div className="port-list">
      {ports.map((name) => (
        <div key={name} className="port-list-item" title={name}>
          <span className="port-list-name">{name}</span>
        </div>
      ))}
    </div>
  );
}

function InterfaceSummary({ inputs, outputs }: { inputs: string[]; outputs: string[] }) {
  return (
    <div className="port-list">
      <div className="property-row">
        <span>inputs</span>
        <code>{String(inputs.length)}</code>
      </div>
      <PortListBody ports={inputs} />
      <div className="property-row">
        <span>outputs</span>
        <code>{String(outputs.length)}</code>
      </div>
      <PortListBody ports={outputs} />
    </div>
  );
}

function parseEndpointForInspector(value: unknown): { node: string; port?: string } | null {
  if (typeof value !== "string" || value.trim().length === 0) return null;
  const trimmed = value.trim();
  const sep = trimmed.includes(".") ? "." : trimmed.includes(":") ? ":" : null;
  if (!sep) return { node: trimmed };
  const idx = trimmed.indexOf(sep);
  const node = trimmed.slice(0, idx);
  const port = trimmed.slice(idx + 1);
  return node ? { node, port } : null;
}

function asTargetListForInspector(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((entry) => (typeof entry === "string" ? [entry] : []));
  }
  if (typeof value === "string") return [value];
  return [];
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function countSavedInitialInputs(lab: LocalLab): number {
  const initial = lab.manifest.runtime?.initial_inputs;
  if (!isObjectRecord(initial)) return 0;
  return Object.values(initial).reduce((total, raw) => {
    if (isObjectRecord(raw)) return total + Object.keys(raw).length;
    return total + 1;
  }, 0);
}

function expandWires(wires: WiringEntry[]): Array<{ from: string; to: string }> {
  const out: Array<{ from: string; to: string }> = [];
  wires.forEach((wire) => {
    const fromRaw = wire.from ?? wire.source;
    if (typeof fromRaw !== "string" || !fromRaw.trim()) return;
    const targets = asTargetListForInspector(wire.to ?? wire.target);
    targets.forEach((to) => {
      const trimmedTarget = to.trim();
      if (!trimmedTarget) return;
      out.push({ from: fromRaw.trim(), to: trimmedTarget });
    });
  });
  return out;
}

function flattenWires(wires: WiringEntry[]): WiringEntry[] {
  return expandWires(wires).map(({ from, to }) => ({ from, to }));
}

function aliasFromWireRef(ref: string): string {
  return parseEndpointForInspector(ref)?.node ?? "";
}

function canAddWire(wires: WiringEntry[], from: string, to: string): boolean {
  const source = from.trim();
  const target = to.trim();
  if (!source || !target || source === target) return false;
  const sourceAlias = aliasFromWireRef(source);
  const targetAlias = aliasFromWireRef(target);
  if (sourceAlias && targetAlias && sourceAlias === targetAlias) return false;
  return !flattenWires(wires).some((entry) => entry.from === source && entry.to === target);
}

function addWire(wires: WiringEntry[], from: string, to: string): WiringEntry[] {
  const flat = flattenWires(wires);
  const source = from.trim();
  const target = to.trim();
  if (!canAddWire(flat, source, target)) return flat;
  return [...flat, { from: source, to: target }];
}

function removeWire(wires: WiringEntry[], from: string, to: string): WiringEntry[] {
  return flattenWires(wires).filter((entry) => !(entry.from === from && entry.to === to));
}

function DescriptorParameterField({
  descriptor,
  value,
  overridden,
  onChange,
}: {
  descriptor: ParameterDescriptor;
  value: string;
  overridden: boolean;
  onChange: (next: string) => void;
}) {
  return (
    <div className="param-field" title={descriptor.description}>
      <div className="param-field-label">
        <span title={descriptor.name}>
          {descriptor.units ? `${descriptor.name} (${descriptor.units})` : descriptor.name}
        </span>
        {overridden ? <span className="param-overridden-dot" title="Overridden">●</span> : null}
      </div>
      <input
        className="param-field-input"
        type="number"
        step="any"
        min={descriptor.min}
        max={descriptor.max}
        value={value}
        placeholder={String(descriptor.value)}
        onChange={(e) => onChange(e.target.value)}
      />
      {(descriptor.min !== undefined || descriptor.max !== undefined) ? (
        <span className="param-bounds-hint">
          {descriptor.min !== undefined ? `min: ${descriptor.min}` : ""}
          {descriptor.min !== undefined && descriptor.max !== undefined ? " · " : ""}
          {descriptor.max !== undefined ? `max: ${descriptor.max}` : ""}
        </span>
      ) : null}
    </div>
  );
}

function ModelInspector({
  lab,
  entry,
  onSave,
}: {
  lab: LocalLab;
  entry: LabModelEntry;
  onSave?: InspectorProps["onSaveModel"];
}) {
  const ports = getModelPorts(lab, entry);
  const descriptors = React.useMemo(() => getModelParameterDescriptors(entry), [entry]);
  const baseParameters = (entry.parameters as Record<string, unknown> | undefined) ?? {};

  // paramValues is a sparse map of edits — it only contains a key when the user has typed
  // something. Untouched descriptors fall back to baseParameters[name] then descriptor.value.
  const [paramValues, setParamValues] = React.useState<Record<string, string>>({});
  const [aliasDraft, setAliasDraft] = React.useState(entry.alias);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  // Reset when the selected entry changes or after a successful save bumps updated_at.
  React.useEffect(() => {
    setParamValues({});
    setAliasDraft(entry.alias);
    setError(null);
    // The deep-equality comparison via JSON keeps this from firing on every render of the parent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry.alias, JSON.stringify(baseParameters)]);

  // Merge sparse edits over the existing override, so untouched descriptors keep whatever the
  // lab manifest already had (or are simply absent if there was no override before).
  const nextParameters: Record<string, unknown> = { ...baseParameters };
  for (const [name, text] of Object.entries(paramValues)) {
    const trimmed = text.trim();
    if (trimmed.length === 0) {
      delete nextParameters[name];
      continue;
    }
    const n = Number(trimmed);
    nextParameters[name] = Number.isFinite(n) && /^-?\d+(\.\d+)?(e[+-]?\d+)?$/i.test(trimmed)
      ? n
      : stringToValue(trimmed, baseParameters[name]);
  }
  const trimmedAlias = aliasDraft.trim();
  const aliasChanged = trimmedAlias.length > 0 && trimmedAlias !== entry.alias;
  const dirty =
    aliasChanged ||
    !recordsEqual(nextParameters, baseParameters);
  const aliasInvalid = aliasDraft.length > 0 && trimmedAlias.length === 0;

  async function handleSave() {
    if (!onSave) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(entry.alias, {
        parameters: nextParameters,
        ...(aliasChanged ? { alias: trimmedAlias } : {}),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="inspector-body">
      <h2>{titleForModel(entry)}</h2>
      <p className="muted">{entry.package || entry.path || entry.alias}</p>

      <section className="property-static">
        <h3 className="property-static-title">Identity</h3>
        {entry.resolved_model?.description ? (
          <p className="muted small">{entry.resolved_model.description}</p>
        ) : null}
        <div className="port-row-fields">
          <label>
            <span>alias</span>
            <input
              value={aliasDraft}
              onChange={(event) => setAliasDraft(event.target.value)}
              spellCheck={false}
              disabled={!onSave}
              aria-label="Model alias"
            />
          </label>
          <div className="property-row">
            <span>version</span>
            <code>{entry.version || "-"}</code>
          </div>
        </div>
        {aliasInvalid ? (
          <div className="property-warning">Alias cannot be empty.</div>
        ) : null}
        {entry.path ? (
          <div className="property-row">
            <span>path</span>
            <code>{entry.path}</code>
          </div>
        ) : null}
        {entry.package ? (
          <div className="property-row">
            <span>package</span>
            <code>{entry.package}</code>
          </div>
        ) : null}
        {entry.resolution_error ? <div className="property-warning">{entry.resolution_error}</div> : null}
      </section>

      <PropertySection title="Interface" count={ports.inputs.length + ports.outputs.length} defaultOpen>
        <InterfaceSummary inputs={ports.inputs} outputs={ports.outputs} />
      </PropertySection>

      <PropertySection title="Parameters" count={descriptors.length} defaultOpen>
        {descriptors.length === 0 ? (
          <p className="muted small">No parameters declared.</p>
        ) : (
          descriptors.map((descriptor) => {
            const overrideValue = baseParameters[descriptor.name];
            const overridden = typeof overrideValue === "number" && Number.isFinite(overrideValue);
            const text =
              paramValues[descriptor.name] !== undefined
                ? paramValues[descriptor.name]
                : overridden
                  ? String(overrideValue)
                  : String(descriptor.value);
            return (
              <DescriptorParameterField
                key={descriptor.name}
                descriptor={descriptor}
                value={text}
                overridden={overridden}
                onChange={(next) =>
                  setParamValues((current) => ({ ...current, [descriptor.name]: next }))
                }
              />
            );
          })
        )}
      </PropertySection>

      {error ? <div className="property-error">{error}</div> : null}

      {onSave ? (
        <div className="property-actions">
          <button className="button primary small" disabled={!dirty || busy} onClick={handleSave}>
            <Save size={12} />
            {busy ? "Saving..." : "Save"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function LabInspector({ lab, entry }: { lab: LocalLab; entry: LabChildEntry }) {
  const baseParameters = (entry.parameters as Record<string, unknown> | undefined) ?? {};
  const ports = getLabPorts(lab, entry);
  return (
    <div className="inspector-body">
      <h2>{titleForLab(entry)}</h2>
      <p className="muted">{entry.package || entry.path || entry.alias}</p>

      <PropertySection title="Identity" defaultOpen>
        <div className="property-row">
          <span>Alias</span>
          <code>{entry.alias}</code>
        </div>
        <div className="property-row">
          <span>Version</span>
          <code>{entry.version || "-"}</code>
        </div>
        <div className="property-row">
          <span>Models</span>
          <code>{String(entry.resolved_space?.model_count ?? "-")}</code>
        </div>
      </PropertySection>

      <PropertySection title="Inputs" count={ports.inputs.length}>
        <PortListBody ports={ports.inputs} />
      </PropertySection>

      <PropertySection title="Outputs" count={ports.outputs.length}>
        <PortListBody ports={ports.outputs} />
      </PropertySection>

      <PropertySection title="Parameters" count={Object.keys(baseParameters).length}>
        {Object.keys(baseParameters).length === 0 ? (
          <p className="muted small">No parameters declared.</p>
        ) : (
          Object.entries(baseParameters).map(([key, val]) => (
            <ParameterField
              key={key}
              name={key}
              original={val}
              value={valueToString(val)}
              onChange={() => {
                /* read-only for nested labs — no save endpoint exposed */
              }}
            />
          ))
        )}
      </PropertySection>
    </div>
  );
}

type WorldDraft = {
  inputs: WorldIoPort[];
  outputs: WorldIoPort[];
  runtime: Record<string, string>;
};

function buildWorldDraft(lab: LocalLab): WorldDraft {
  const runtime = (lab.manifest.runtime as Record<string, unknown> | undefined) ?? {};
  return {
    inputs: (lab.manifest.io?.inputs ?? []).map((p) => ({ name: p.name, maps_to: p.maps_to })),
    outputs: (lab.manifest.io?.outputs ?? []).map((p) => ({ name: p.name, maps_to: p.maps_to })),
    runtime: Object.fromEntries(Object.entries(runtime).map(([k, v]) => [k, valueToString(v)])),
  };
}

function collectComponentEndpoints(
  lab: LocalLab,
  side: "inputs" | "outputs",
): string[] {
  const refs: string[] = [];
  const seen = new Set<string>();
  const push = (alias: string, port: string) => {
    const ref = `${alias}.${port}`;
    if (seen.has(ref)) return;
    seen.add(ref);
    refs.push(ref);
  };
  for (const entry of lab.manifest.models ?? []) {
    const ports = getModelPorts(lab, entry);
    for (const port of ports[side]) push(entry.alias, port);
  }
  for (const entry of lab.manifest.children ?? []) {
    const ports = getLabPorts(lab, entry);
    for (const port of ports[side]) push(entry.alias, port);
  }
  return refs;
}

type ConnectionDraft = {
  source: string;
  target: string;
};

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function WorldConnectionsSection({
  lab,
  inputEndpoints,
  outputEndpoints,
  onSave,
}: {
  lab: LocalLab;
  inputEndpoints: string[];
  outputEndpoints: string[];
  onSave?: InspectorProps["onSaveWorld"];
}) {
  const wires = lab.manifest.wiring ?? [];
  const connections = React.useMemo(() => flattenWires(wires), [wires]);
  const [drafts, setDrafts] = React.useState<ConnectionDraft[]>([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setDrafts([]);
    setError(null);
  }, [lab.id, lab.updated_at]);

  async function saveWiring(nextWiring: WiringEntry[]) {
    if (!onSave) return;
    setSaving(true);
    setError(null);
    try {
      await onSave({ wiring: nextWiring });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  function appendDraft() {
    setDrafts((current) => [...current, { source: "", target: "" }]);
  }

  function removeDraft(index: number) {
    setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function updateDraft(index: number, key: keyof ConnectionDraft, value: string, draft: ConnectionDraft) {
    const nextDraft = { ...draft, [key]: value };
    if (nextDraft.source && nextDraft.target) {
      setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index));
      if (canAddWire(wires, nextDraft.source, nextDraft.target)) {
        void saveWiring(addWire(wires, nextDraft.source, nextDraft.target));
      }
      return;
    }
    setDrafts((current) =>
      current.map((entry, itemIndex) => (itemIndex === index ? nextDraft : entry)),
    );
  }

  function removeConnection(from: string, to: string) {
    void saveWiring(removeWire(wires, from, to));
  }

  return (
    <PropertySection title="Connections">
      <div className="connection-section">
        <p className="connection-description">
          Connect an output from one component to an input on another component.
        </p>

        {connections.length > 0 || drafts.length > 0 ? (
          <div className="connection-list">
            {connections.map((connection, index) => (
              <div
                key={`${connection.from}->${connection.to}-${index}`}
                className="connection-row"
              >
                <div className="connection-row-body">
                  <Cable size={12} className="connection-icon" aria-hidden="true" />
                  <code className="connection-ref">{connection.from}</code>
                  <ArrowRight size={12} className="connection-arrow" aria-label="to" />
                  <code className="connection-ref">{connection.to}</code>
                </div>
                {onSave ? (
                  <button
                    type="button"
                    className="icon-button tiny"
                    aria-label={`Remove connection ${connection.from} to ${connection.to}`}
                    title="Remove connection"
                    disabled={saving}
                    onClick={() => removeConnection(connection.from, connection.to)}
                  >
                    <Trash2 size={11} />
                  </button>
                ) : null}
              </div>
            ))}

            {drafts.map((draft, index) => {
              const sourceAlias = aliasFromWireRef(draft.source);
              const targetOptions = inputEndpoints.filter((ref) => {
                const targetAlias = aliasFromWireRef(ref);
                return !sourceAlias || !targetAlias || targetAlias !== sourceAlias;
              });
              return (
                <div key={`draft-${index}`} className="port-row connection-draft">
                  <div className="port-row-fields">
                    <label>
                      <span>source</span>
                      <select
                        value={draft.source}
                        aria-label={`Draft connection ${index + 1} source`}
                        disabled={!onSave || saving}
                        onChange={(event) =>
                          updateDraft(index, "source", event.target.value, draft)
                        }
                      >
                        <option value="">Source output</option>
                        {outputEndpoints.map((ref) => (
                          <option key={ref} value={ref}>
                            {ref}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>target</span>
                      <select
                        value={draft.target}
                        aria-label={`Draft connection ${index + 1} target`}
                        disabled={!onSave || saving}
                        onChange={(event) =>
                          updateDraft(index, "target", event.target.value, draft)
                        }
                      >
                        <option value="">Target input</option>
                        {targetOptions.map((ref) => (
                          <option key={ref} value={ref}>
                            {ref}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <button
                    type="button"
                    className="icon-button tiny"
                    aria-label={`Remove draft connection ${index + 1}`}
                    title="Remove draft connection"
                    disabled={saving}
                    onClick={() => removeDraft(index)}
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="muted small">No connections yet.</p>
        )}

        {onSave ? (
          <button
            type="button"
            className="link-button connection-add-button"
            aria-label="Add world connection"
            disabled={saving}
            onClick={appendDraft}
          >
            <Plus size={11} /> Add connection
          </button>
        ) : null}

        {error ? <div className="property-error">{error}</div> : null}
      </div>
    </PropertySection>
  );
}

function WorldInspector({
  lab,
  onSave,
}: {
  lab: LocalLab;
  onSave?: InspectorProps["onSaveWorld"];
}) {
  const baseRuntime = (lab.manifest.runtime as Record<string, unknown> | undefined) ?? {};
  const [draft, setDraft] = React.useState<WorldDraft>(() => buildWorldDraft(lab));
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const inputEndpoints = React.useMemo(
    () => collectComponentEndpoints(lab, "inputs"),
    [lab],
  );
  const outputEndpoints = React.useMemo(
    () => collectComponentEndpoints(lab, "outputs"),
    [lab],
  );
  const savedInputCount = React.useMemo(() => countSavedInitialInputs(lab), [lab]);

  React.useEffect(() => {
    setDraft(buildWorldDraft(lab));
    setError(null);
  }, [lab.id, lab.updated_at]);

  function buildRuntime(): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    for (const [key, text] of Object.entries(draft.runtime)) {
      out[key] = stringToValue(text, baseRuntime[key]);
    }
    return out;
  }

  const dirty = React.useMemo(() => {
    const baseInputs = (lab.manifest.io?.inputs ?? []).map((p) => `${p.name}=${p.maps_to}`).join("|");
    const baseOutputs = (lab.manifest.io?.outputs ?? []).map((p) => `${p.name}=${p.maps_to}`).join("|");
    const draftInputs = draft.inputs.map((p) => `${p.name}=${p.maps_to}`).join("|");
    const draftOutputs = draft.outputs.map((p) => `${p.name}=${p.maps_to}`).join("|");
    if (baseInputs !== draftInputs || baseOutputs !== draftOutputs) return true;
    const baseRuntimeStr = JSON.stringify(baseRuntime);
    const nextRuntimeStr = JSON.stringify(buildRuntime());
    return baseRuntimeStr !== nextRuntimeStr;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, lab]);

  async function handleSave() {
    if (!onSave) return;
    setBusy(true);
    setError(null);
    try {
      await onSave({ inputs: draft.inputs, outputs: draft.outputs, runtime: buildRuntime() });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function updatePort(side: "inputs" | "outputs", index: number, key: "name" | "maps_to", value: string) {
    setDraft((current) => ({
      ...current,
      [side]: current[side].map((p, i) => (i === index ? { ...p, [key]: value } : p)),
    }));
  }
  function addPort(side: "inputs" | "outputs") {
    setDraft((current) => ({ ...current, [side]: [...current[side], { name: "", maps_to: "" }] }));
  }
  function removePort(side: "inputs" | "outputs", index: number) {
    setDraft((current) => ({
      ...current,
      [side]: current[side].filter((_, i) => i !== index),
    }));
  }
  function updateRuntime(key: string, value: string) {
    setDraft((current) => ({ ...current, runtime: { ...current.runtime, [key]: value } }));
  }

  return (
    <div className="inspector-body">
      <h2>World</h2>
      <p className="muted">{lab.description || "Lab runtime and public interface"}</p>

      <PropertySection title="Runtime" defaultOpen>
        {savedInputCount > 0 ? (
          <div className="property-warning">
            {savedInputCount} saved input default{savedInputCount === 1 ? "" : "s"} remain active
            for compatibility. Edit the manifest to change them.
          </div>
        ) : null}
        {Object.keys(draft.runtime).length === 0 ? (
          <p className="muted small">No runtime config.</p>
        ) : (
          Object.entries(draft.runtime).map(([key, val]) => (
            <ParameterField
              key={key}
              name={key}
              original={baseRuntime[key]}
              value={val}
              onChange={(next) => updateRuntime(key, next)}
            />
          ))
        )}
      </PropertySection>

      <WorldConnectionsSection
        lab={lab}
        inputEndpoints={inputEndpoints}
        outputEndpoints={outputEndpoints}
        onSave={onSave}
      />

      <PropertySection title="World inputs" count={draft.inputs.length}>
        {draft.inputs.map((port, index) => (
          <PortRow
            key={index}
            port={port}
            endpoints={inputEndpoints}
            usedEndpoints={draft.inputs}
            onChange={(key, value) => updatePort("inputs", index, key, value)}
            onRemove={onSave ? () => removePort("inputs", index) : undefined}
          />
        ))}
        {onSave ? (
          <button type="button" className="link-button" onClick={() => addPort("inputs")}>
            <Plus size={11} /> Add input
          </button>
        ) : null}
      </PropertySection>

      <PropertySection title="World outputs" count={draft.outputs.length}>
        {draft.outputs.map((port, index) => (
          <PortRow
            key={index}
            port={port}
            endpoints={outputEndpoints}
            usedEndpoints={draft.outputs}
            onChange={(key, value) => updatePort("outputs", index, key, value)}
            onRemove={onSave ? () => removePort("outputs", index) : undefined}
          />
        ))}
        {onSave ? (
          <button type="button" className="link-button" onClick={() => addPort("outputs")}>
            <Plus size={11} /> Add output
          </button>
        ) : null}
      </PropertySection>

      {error ? <div className="property-error">{error}</div> : null}

      {onSave ? (
        <div className="property-actions">
          <button className="button primary small" disabled={!dirty || busy} onClick={handleSave}>
            <Save size={12} />
            {busy ? "Saving..." : "Save"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function PortRow({
  port,
  endpoints,
  usedEndpoints,
  onChange,
  onRemove,
}: {
  port: WorldIoPort;
  endpoints: string[];
  usedEndpoints: WorldIoPort[];
  onChange: (key: "name" | "maps_to", value: string) => void;
  onRemove?: () => void;
}) {
  const usedByOthers = new Set(
    usedEndpoints.filter((entry) => entry !== port).map((entry) => entry.maps_to).filter(Boolean),
  );
  const selectable = endpoints.filter(
    (ref) => ref === port.maps_to || !usedByOthers.has(ref),
  );
  const currentInList = endpoints.includes(port.maps_to);
  return (
    <div className="port-row">
      <div className="port-row-fields">
        <label>
          <span>name</span>
          <input value={port.name} onChange={(e) => onChange("name", e.target.value)} spellCheck={false} />
        </label>
        <label>
          <span>maps_to</span>
          <select
            value={port.maps_to}
            onChange={(e) => onChange("maps_to", e.target.value)}
          >
            <option value="">alias.port</option>
            {!currentInList && port.maps_to ? (
              <option value={port.maps_to}>{port.maps_to}</option>
            ) : null}
            {selectable.map((ref) => (
              <option key={ref} value={ref}>
                {ref}
              </option>
            ))}
          </select>
        </label>
      </div>
      {onRemove ? (
        <button type="button" className="icon-button tiny" title="Remove" onClick={onRemove}>
          <Trash2 size={11} />
        </button>
      ) : null}
    </div>
  );
}

export function Inspector(props: InspectorProps) {
  const { lab, selection, onClose, onSaveModel, onSaveWorld } = props;
  if (!lab || selection.kind === "none") return null;

  return (
    <aside className="inspector-panel">
      <div className="panel-header">
        <span>Properties</span>
        <button className="icon-button small" onClick={onClose} title="Clear selection">
          <X size={13} />
        </button>
      </div>
      {selection.kind === "world" ? <WorldInspector lab={lab} onSave={onSaveWorld} /> : null}
      {selection.kind === "model"
        ? (() => {
            const entry = lab.manifest.models?.find((m) => m.alias === selection.id);
            if (!entry) return <div className="muted inspector-body">Model not found.</div>;
            return (
              <ModelInspector
                lab={lab}
                entry={entry}
                onSave={onSaveModel}
              />
            );
          })()
        : null}
      {selection.kind === "lab"
        ? (() => {
            const entry = lab.manifest.children?.find((c) => c.alias === selection.id);
            if (!entry) return <div className="muted inspector-body">Lab not found.</div>;
            return <LabInspector lab={lab} entry={entry} />;
          })()
        : null}
    </aside>
  );
}
