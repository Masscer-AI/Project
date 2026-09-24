import { ReactNode } from "react";
import { OpenSidebarButton } from "../OpenSidebarButton/OpenSidebarButton";

export function AppHeader({
  children,
  right,
  flush = false,
}: {
  children?: ReactNode;
  right?: ReactNode;
  flush?: boolean;
}) {
  return (
    <div
      className="flex items-center justify-between p-2 md:p-4 rounded-none md:rounded-xl w-full shadow-lg z-10 gap-2 md:gap-3 min-w-0 shrink-0"
      style={{
        background: "var(--bg-contrast-color)",
        border: "1px solid var(--hovered-color)",
        marginBottom: flush ? 0 : 16,
      }}
    >
      <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
        <OpenSidebarButton flush />
        {children}
      </div>
      {right}
    </div>
  );
}
