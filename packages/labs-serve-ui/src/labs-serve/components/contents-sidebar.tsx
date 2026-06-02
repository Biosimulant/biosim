import * as React from "react";
import { Activity, FlaskConical, GitBranch, Search } from "lucide-react";
import type { LocalLab, Selection } from "../types";
import { titleForLab, titleForModel } from "../lib/graph";

export type ContentsSidebarProps = {
  lab: LocalLab | null;
  selection: Selection;
  onSelect: (sel: Selection) => void;
};

export function ContentsSidebar({ lab, selection, onSelect }: ContentsSidebarProps) {
  const [query, setQuery] = React.useState("");
  const models = lab?.manifest.models ?? [];
  const children = lab?.manifest.children ?? [];
  const lower = query.toLowerCase();
  const matchedModels = models.filter(
    (entry) =>
      entry.alias.toLowerCase().includes(lower) ||
      titleForModel(entry).toLowerCase().includes(lower),
  );
  const matchedChildren = children.filter(
    (entry) =>
      entry.alias.toLowerCase().includes(lower) ||
      titleForLab(entry).toLowerCase().includes(lower),
  );

  return (
    <aside className="left-panel">
      <label className="search-box">
        <Search size={13} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search lab"
        />
      </label>
      <div className="sidebar-section">
        <button
          className={`tree-item ${selection.kind === "world" ? "active" : ""}`}
          onClick={() => onSelect({ kind: "world" })}
        >
          <Activity size={13} className="tree-item-icon" />
          <div className="tree-item-text">
            <div className="tree-item-title">World</div>
            <div className="tree-item-subtitle">{lab?.manifest.runtime ? "runtime" : "local"}</div>
          </div>
        </button>
        {matchedModels.map((entry) => (
          <button
            key={entry.alias}
            className={`tree-item ${selection.kind === "model" && selection.id === entry.alias ? "active" : ""}`}
            onClick={() => onSelect({ kind: "model", id: entry.alias })}
            title={titleForModel(entry)}
          >
            <FlaskConical size={13} className="tree-item-icon" />
            <div className="tree-item-text">
              <div className="tree-item-title">{titleForModel(entry)}</div>
              <div className="tree-item-subtitle">{entry.alias}</div>
            </div>
          </button>
        ))}
        {matchedChildren.map((entry) => (
          <button
            key={entry.alias}
            className={`tree-item ${selection.kind === "lab" && selection.id === entry.alias ? "active" : ""}`}
            onClick={() => onSelect({ kind: "lab", id: entry.alias })}
            title={titleForLab(entry)}
          >
            <GitBranch size={13} className="tree-item-icon" />
            <div className="tree-item-text">
              <div className="tree-item-title">{titleForLab(entry)}</div>
              <div className="tree-item-subtitle">{entry.alias}</div>
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}
