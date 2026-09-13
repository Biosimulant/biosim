import {
  ArrowsCounterClockwiseIcon,
  CircleNotchIcon,
  FlaskIcon,
  MoonIcon,
  PlayIcon,
  SidebarSimpleIcon,
  StopCircleIcon,
  SunIcon,
} from "@phosphor-icons/react";
import type { LocalLab, LocalRun } from "../types";
import { isActive } from "../hooks/use-runs";
import type { ThemeMode } from "../hooks/use-theme";

export type HeaderProps = {
  lab: LocalLab | null;
  activeRun: LocalRun | null;
  busy: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onRefresh: () => void;
  onRunClick: () => void;
  onCancel: () => void;
  theme: ThemeMode;
  onThemeChange: (next: ThemeMode) => void;
  saved: boolean;
};

function nextTheme(current: ThemeMode): ThemeMode {
  if (current === "system") return "light";
  if (current === "light") return "dark";
  return "system";
}

export function Header(props: HeaderProps) {
  const {
    lab,
    activeRun,
    busy,
    onToggleLeft,
    onToggleRight,
    onRefresh,
    onRunClick,
    onCancel,
    theme,
    onThemeChange,
    saved,
  } = props;

  const running = isActive(activeRun);
  const cancelling = activeRun?.status === "cancelling";

  return (
    <header className="command-bar">
      <button
        className="icon-button"
        title="Toggle contents"
        onClick={onToggleLeft}
        aria-label="Toggle contents sidebar"
      >
        <SidebarSimpleIcon size={16} />
      </button>
      <div className="command-title">
        <FlaskIcon size={18} />
        <div>
          <h1>{lab?.title || "Biosimulant Lab"}</h1>
          <p>{lab?.file_path || lab?.id || "Loading lab..."}</p>
        </div>
      </div>
      <div className="command-actions">
        <span className={`saved-indicator ${saved ? "ok" : "dirty"}`}>{saved ? "Saved" : "Unsaved"}</span>
        {running ? (
          <button className="button danger" disabled={busy || cancelling} onClick={onCancel}>
            {cancelling ? <CircleNotchIcon size={14} className="spin" /> : <StopCircleIcon size={14} />}
            {cancelling ? "Cancelling" : "Cancel"}
          </button>
        ) : (
          <button className="button primary" disabled={busy} onClick={onRunClick}>
            {busy ? <CircleNotchIcon size={14} className="spin" /> : <PlayIcon size={14} />}
            Run
          </button>
        )}
        <button className="icon-button" title="Refresh" onClick={onRefresh}>
          <ArrowsCounterClockwiseIcon size={15} />
        </button>
        <button
          className="icon-button"
          title={`Theme: ${theme}`}
          onClick={() => onThemeChange(nextTheme(theme))}
        >
          {theme === "dark" ? <MoonIcon size={15} /> : <SunIcon size={15} />}
        </button>
        <button
          className="icon-button"
          title="Toggle run panel"
          onClick={onToggleRight}
          aria-label="Toggle run sidebar"
        >
          <SidebarSimpleIcon size={16} />
        </button>
      </div>
    </header>
  );
}
