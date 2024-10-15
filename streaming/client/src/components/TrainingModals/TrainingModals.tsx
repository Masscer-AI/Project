import React from "react";
import { DocumentsModal } from "../DocumentsModal/DocumentsModal";
import { useStore } from "../../modules/store";

export const TrainingModals = () => {
  const { openedModals, setOpenedModals } = useStore((s) => ({
    openedModals: s.openedModals,
    setOpenedModals: s.setOpenedModals,
  }));

  console.log(openedModals);

  return (
    <>
      {openedModals.includes("documents") && (
        <DocumentsModal
          visible={true}
          hide={() => setOpenedModals({ action: "remove", name: "documents" })}
        />
      )}
    </>
  );
};
