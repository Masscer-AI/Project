import React, { useEffect } from "react";
import MindMapper from "../../components/Plugins/MindMapper";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { ChatHeader } from "../../components/ChatHeader/ChatHeader";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

export default function WorkflowsPage() {
  const { chatState, startup } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
  }));

  useEffect(() => {
    startup();
  }, []);

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <MindMapper />
    </main>
  );
}
