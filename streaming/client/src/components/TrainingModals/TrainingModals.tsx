import React from "react";
import { DocumentsModal } from "../DocumentsModal/DocumentsModal";
import { useStore } from "../../modules/store";
import { CompletionsModal } from "../CompletionsModal/CompletionsModal";
import { Settings } from "../Settings/Settings";

export const TrainingModals = () => {
  const { openedModals, setOpenedModals } = useStore((s) => ({
    openedModals: s.openedModals,
    setOpenedModals: s.setOpenedModals,
  }));

  return (
    <>
      {openedModals.includes("documents") && (
        <DocumentsModal
          visible={true}
          hide={() => setOpenedModals({ action: "remove", name: "documents" })}
        />
      )}
      {openedModals.includes("completions") && (
        <CompletionsModal
          visible={true}
          hide={() =>
            setOpenedModals({ action: "remove", name: "completions" })
          }
        />
      )}
      {openedModals.includes("settings") && <Settings />}
    </>
  );
};
