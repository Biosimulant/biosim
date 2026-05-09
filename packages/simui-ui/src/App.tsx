import React from "react";
import { ApiProvider } from "./app/providers";
import { UiProvider } from "./app/ui";
import type { SimulationApi } from "./lib/api";
import DesktopLabShell from "./components/DesktopLabShell";

type AppMode = "simulation" | "editor";

export interface SimuiAppProps {
  api?: SimulationApi;
  className?: string;
  style?: React.CSSProperties;
  height?: string;
  initialMode?: AppMode;
  hideHeader?: boolean;
  onConnectionChange?: (connected: boolean) => void;
  headerLeft?: React.ReactNode;
  headerRight?: React.ReactNode;
  sidebarAction?: React.ReactNode;
}

export const SimuiApp: React.FC<SimuiAppProps> = ({
  api,
  className,
  style,
  height = "100vh",
  hideHeader,
  onConnectionChange,
  headerLeft,
  headerRight,
  sidebarAction,
}) => {
  const combinedClassName = className ? `simui-root ${className}` : "simui-root";
  return (
    <div className={combinedClassName} style={{ height, ...style }}>
      <ApiProvider api={api}>
        <UiProvider>
          <DesktopLabShell
            hideHeader={hideHeader}
            onConnectionChange={onConnectionChange}
            headerLeft={headerLeft}
            headerRight={headerRight}
            sidebarAction={sidebarAction}
          />
        </UiProvider>
      </ApiProvider>
    </div>
  );
};

// Backwards-compatible export used by the static bundle entrypoint.
export const App: React.FC = () => <SimuiApp />;
