import { ReactNode } from "react";
import { useStore } from "../../modules/store";
import { AppHeader } from "../AppHeader/AppHeader";
import { Sidebar } from "../Sidebar/Sidebar";

export function AppPage({
  title,
  children,
  right,
  pad = true,
}: {
  title?: ReactNode;
  children: ReactNode;
  right?: ReactNode;
  pad?: boolean;
}) {
  const isSidebarOpened = useStore((s) => s.chatState.isSidebarOpened);

  return (
    <main
      className="flex relative h-screen w-full overflow-hidden"
      style={{ backgroundColor: "var(--bg-color)" }}
    >
      {isSidebarOpened && <Sidebar />}
      <div className="flex min-h-0 min-w-0 flex-col h-screen w-full relative z-10 overflow-hidden">
        <AppHeader title={title} right={right} flush edgeToEdge />
        <div
          className={
            pad
              ? "flex-1 min-h-0 overflow-y-auto px-4 py-4 md:px-6 md:py-6"
              : "flex-1 min-h-0 overflow-hidden"
          }
        >
          {children}
        </div>
      </div>
    </main>
  );
}
