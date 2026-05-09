import React, { useEffect, useMemo, useState } from "react";
import type { Structure3DAnnotation, Structure3DData, StructureSource } from "../types/api";
import { resolveConfig } from "../lib/config";

type Structure3DProps = {
  data: Record<string, unknown>;
  isFullscreen?: boolean;
};

type Atom = {
  id: number;
  name: string;
  element: string;
  residue: string;
  chain: string;
  sequence: number;
  x: number;
  y: number;
  z: number;
};

type ProjectedAtom = Atom & {
  px: number;
  py: number;
  pz: number;
  radius: number;
};

const ELEMENT_COLORS: Record<string, string> = {
  C: "#64748b",
  H: "#cbd5e1",
  N: "#2563eb",
  O: "#dc2626",
  S: "#ca8a04",
  P: "#f97316",
  FE: "#b45309",
  MG: "#16a34a",
  ZN: "#7c3aed",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeSource(value: unknown): StructureSource | null {
  if (!isRecord(value) || typeof value.kind !== "string") return null;
  if (value.kind === "url" && typeof value.url === "string" && value.url.trim()) {
    return { kind: "url", url: value.url };
  }
  if (value.kind === "artifact" && typeof value.artifact_id === "string" && value.artifact_id.trim()) {
    return { kind: "artifact", artifact_id: value.artifact_id };
  }
  return null;
}

function normalizeAnnotations(value: unknown): Structure3DAnnotation[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!isRecord(entry) || typeof entry.label !== "string") return [];
    const annotationValue = entry.value;
    if (
      typeof annotationValue !== "string" &&
      typeof annotationValue !== "number" &&
      typeof annotationValue !== "boolean"
    ) {
      return [];
    }
    return [{ label: entry.label, value: annotationValue }];
  });
}

function normalizeStructureData(value: Record<string, unknown>): Structure3DData | null {
  const source = normalizeSource(value.source);
  const format = value.format === "pdb" ? "pdb" : value.format === "mmcif" ? "mmcif" : null;
  if (!source || !format) return null;

  return {
    title: typeof value.title === "string" ? value.title : undefined,
    source,
    format,
    description: typeof value.description === "string" ? value.description : undefined,
    annotations: normalizeAnnotations(value.annotations),
    initial_view: isRecord(value.initial_view) ? value.initial_view : undefined,
  };
}

function resolveStructureUrl(source: StructureSource): string {
  if (source.kind === "url") return source.url;
  const baseUrl = resolveConfig().baseUrl;
  return `${baseUrl}/api/artifacts/${encodeURIComponent(source.artifact_id)}`;
}

function parseElement(line: string, atomName: string): string {
  const elementField = line.slice(76, 78).trim().toUpperCase();
  if (elementField) return elementField;
  const inferred = atomName.replace(/[^A-Za-z]/g, "").slice(0, 2).toUpperCase();
  return inferred.length > 1 && ELEMENT_COLORS[inferred] ? inferred : inferred.slice(0, 1) || "C";
}

function parsePdb(content: string): Atom[] {
  const atoms: Atom[] = [];
  for (const line of content.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    const x = Number.parseFloat(line.slice(30, 38));
    const y = Number.parseFloat(line.slice(38, 46));
    const z = Number.parseFloat(line.slice(46, 54));
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    const name = line.slice(12, 16).trim();
    atoms.push({
      id: atoms.length,
      name,
      element: parseElement(line, name),
      residue: line.slice(17, 20).trim() || "UNK",
      chain: line.slice(21, 22).trim() || "A",
      sequence: Number.parseInt(line.slice(22, 26), 10) || atoms.length,
      x,
      y,
      z,
    });
  }
  return atoms;
}

function tokenizeCifLine(line: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let quote: "'" | "\"" | null = null;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]!;
    if (quote) {
      if (char === quote) {
        quote = null;
      } else {
        current += char;
      }
      continue;
    }
    if (char === "'" || char === "\"") {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = "";
      }
      continue;
    }
    current += char;
  }
  if (current) tokens.push(current);
  return tokens;
}

function parseMmcif(content: string): Atom[] {
  const lines = content.split(/\r?\n/);
  const atoms: Atom[] = [];
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index]?.trim() !== "loop_") continue;

    const headers: string[] = [];
    let cursor = index + 1;
    while (cursor < lines.length && lines[cursor]?.trim().startsWith("_atom_site.")) {
      headers.push(lines[cursor]!.trim());
      cursor += 1;
    }
    if (headers.length === 0) continue;

    const headerIndex = (name: string) => headers.findIndex((header) => header.endsWith(`.${name}`));
    const xIndex = headerIndex("Cartn_x");
    const yIndex = headerIndex("Cartn_y");
    const zIndex = headerIndex("Cartn_z");
    if (xIndex < 0 || yIndex < 0 || zIndex < 0) continue;

    const atomIndex = headerIndex("label_atom_id");
    const elementIndex = headerIndex("type_symbol");
    const residueIndex = headerIndex("label_comp_id");
    const chainIndex = headerIndex("label_asym_id");
    const seqIndex = headerIndex("label_seq_id");

    while (cursor < lines.length) {
      const line = lines[cursor]!.trim();
      if (!line || line.startsWith("#") || line.startsWith("_") || line === "loop_") break;
      const tokens = tokenizeCifLine(line);
      if (tokens.length >= headers.length) {
        const x = Number.parseFloat(tokens[xIndex]!);
        const y = Number.parseFloat(tokens[yIndex]!);
        const z = Number.parseFloat(tokens[zIndex]!);
        if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z)) {
          const name = atomIndex >= 0 ? tokens[atomIndex]! : "";
          atoms.push({
            id: atoms.length,
            name,
            element: (elementIndex >= 0 ? tokens[elementIndex]! : name.slice(0, 1)).toUpperCase() || "C",
            residue: residueIndex >= 0 ? tokens[residueIndex]! : "UNK",
            chain: chainIndex >= 0 ? tokens[chainIndex]! : "A",
            sequence: seqIndex >= 0 ? Number.parseInt(tokens[seqIndex]!, 10) || atoms.length : atoms.length,
            x,
            y,
            z,
          });
        }
      }
      cursor += 1;
    }
  }
  return atoms;
}

function parseStructure(content: string, format: Structure3DData["format"]): Atom[] {
  return format === "pdb" ? parsePdb(content) : parseMmcif(content);
}

function isBackbone(atom: Atom): boolean {
  return atom.name === "CA" || atom.name === "P" || atom.name === "C4'" || atom.name === "C4*";
}

function selectDisplayAtoms(atoms: Atom[]): Atom[] {
  if (atoms.length <= 900) return atoms;
  const backbone = atoms.filter(isBackbone);
  if (backbone.length >= 12) return backbone.slice(0, 1800);
  const step = Math.ceil(atoms.length / 900);
  return atoms.filter((_, index) => index % step === 0);
}

function projectAtoms(atoms: Atom[], width: number, height: number): ProjectedAtom[] {
  if (atoms.length === 0) return [];
  const center = atoms.reduce(
    (acc, atom) => ({ x: acc.x + atom.x, y: acc.y + atom.y, z: acc.z + atom.z }),
    { x: 0, y: 0, z: 0 },
  );
  center.x /= atoms.length;
  center.y /= atoms.length;
  center.z /= atoms.length;

  const rotX = -0.64;
  const rotY = 0.78;
  const sinX = Math.sin(rotX);
  const cosX = Math.cos(rotX);
  const sinY = Math.sin(rotY);
  const cosY = Math.cos(rotY);
  const rotated = atoms.map((atom) => {
    const tx = atom.x - center.x;
    const ty = atom.y - center.y;
    const tz = atom.z - center.z;
    const x1 = tx * cosY + tz * sinY;
    const z1 = -tx * sinY + tz * cosY;
    const y2 = ty * cosX - z1 * sinX;
    const z2 = ty * sinX + z1 * cosX;
    return { atom, x: x1, y: y2, z: z2 };
  });

  const maxSpan = Math.max(
    1,
    ...rotated.map((entry) => Math.abs(entry.x)),
    ...rotated.map((entry) => Math.abs(entry.y)),
  );
  const scale = Math.min(width, height) * 0.42 / maxSpan;
  const minZ = Math.min(...rotated.map((entry) => entry.z));
  const maxZ = Math.max(...rotated.map((entry) => entry.z));
  const zSpan = Math.max(1, maxZ - minZ);

  return rotated
    .map(({ atom, x, y, z }) => ({
      ...atom,
      px: width / 2 + x * scale,
      py: height / 2 - y * scale,
      pz: (z - minZ) / zSpan,
      radius: 2.8 + ((z - minZ) / zSpan) * 4.2,
    }))
    .sort((a, b) => a.pz - b.pz);
}

function buildTracePairs(atoms: ProjectedAtom[]): Array<[ProjectedAtom, ProjectedAtom]> {
  const trace = atoms.filter(isBackbone);
  if (trace.length < 2) return [];
  return trace.flatMap((atom, index) => {
    const next = trace[index + 1];
    if (!next || atom.chain !== next.chain) return [];
    const dx = atom.x - next.x;
    const dy = atom.y - next.y;
    const dz = atom.z - next.z;
    const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
    return distance <= 8 ? [[atom, next] as [ProjectedAtom, ProjectedAtom]] : [];
  });
}

function atomColor(atom: Atom): string {
  return ELEMENT_COLORS[atom.element] || ELEMENT_COLORS[atom.element.slice(0, 1)] || "#64748b";
}

function structureStats(atoms: Atom[]) {
  const chains = new Set(atoms.map((atom) => atom.chain));
  const residues = new Set(atoms.map((atom) => `${atom.chain}:${atom.sequence}:${atom.residue}`));
  return { chains: chains.size, residues: residues.size };
}

export default function Structure3D({ data, isFullscreen = false }: Structure3DProps) {
  const normalized = useMemo(() => normalizeStructureData(data), [data]);
  const [atoms, setAtoms] = useState<Atom[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!normalized) {
      setStatus("error");
      setError("Structure payload is missing a supported source or format.");
      return;
    }

    const structure = normalized;
    let cancelled = false;
    async function loadStructure() {
      setStatus("loading");
      setError(null);
      setAtoms([]);
      try {
        const response = await fetch(resolveStructureUrl(structure.source));
        if (!response.ok) throw new Error(`Structure request failed (${response.status})`);
        const content = await response.text();
        const parsedAtoms = parseStructure(content, structure.format);
        if (parsedAtoms.length === 0) throw new Error("No atom coordinates found in structure file");
        if (!cancelled) {
          setAtoms(parsedAtoms);
          setStatus("ready");
        }
      } catch (loadError) {
        if (cancelled) return;
        setStatus("error");
        setError(loadError instanceof Error ? loadError.message : "Failed to load structure");
      }
    }

    void loadStructure();
    return () => {
      cancelled = true;
    };
  }, [normalized]);

  if (!normalized) {
    return <div className="error-message"><p>Structure payload is missing a supported source or format.</p></div>;
  }

  const width = 860;
  const height = isFullscreen ? 560 : 360;
  const displayAtoms = selectDisplayAtoms(atoms);
  const projectedAtoms = projectAtoms(displayAtoms, width, height);
  const tracePairs = buildTracePairs(projectedAtoms);
  const stats = structureStats(atoms);

  return (
    <div className="structure3d-renderer">
      <div className="structure3d-viewer">
        <svg
          className="structure3d-viewer-mount"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={normalized.title ?? "3D structure preview"}
        >
          <defs>
            <radialGradient id="structure-atom-shade">
              <stop offset="0%" stopColor="#fff" stopOpacity="0.55" />
              <stop offset="42%" stopColor="#fff" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#000" stopOpacity="0.18" />
            </radialGradient>
          </defs>
          <rect width={width} height={height} rx="0" fill="var(--structure-bg, #0f172a)" />
          {tracePairs.map(([source, target]) => (
            <line
              key={`${source.id}-${target.id}`}
              x1={source.px}
              y1={source.py}
              x2={target.px}
              y2={target.py}
              stroke="var(--primary-muted)"
              strokeOpacity={0.22 + Math.max(source.pz, target.pz) * 0.55}
              strokeWidth={2}
            />
          ))}
          {projectedAtoms.map((atom) => (
            <g key={atom.id}>
              <circle
                cx={atom.px}
                cy={atom.py}
                r={atom.radius}
                fill={atomColor(atom)}
                fillOpacity={0.5 + atom.pz * 0.45}
              />
              <circle cx={atom.px} cy={atom.py} r={atom.radius} fill="url(#structure-atom-shade)" />
            </g>
          ))}
        </svg>
        {status !== "ready" && (
          <div className="structure3d-status">
            {status === "loading" || status === "idle" ? "Loading structure..." : error ?? "Structure failed to load"}
          </div>
        )}
      </div>
      <div className="structure3d-annotations">
        <div className="structure3d-annotation">
          <div>Atoms</div>
          <strong>{atoms.length.toLocaleString()}</strong>
        </div>
        <div className="structure3d-annotation">
          <div>Residues</div>
          <strong>{stats.residues.toLocaleString()}</strong>
        </div>
        <div className="structure3d-annotation">
          <div>Chains</div>
          <strong>{stats.chains.toLocaleString()}</strong>
        </div>
        {normalized.annotations?.map((annotation) => (
          <div key={annotation.label} className="structure3d-annotation">
            <div>{annotation.label}</div>
            <strong>{String(annotation.value)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
