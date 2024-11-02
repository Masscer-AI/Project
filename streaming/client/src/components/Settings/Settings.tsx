import React from "react";
import { Modal } from "../Modal/Modal";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { LanguageSelector } from "../LanguageSelector/LanguageSelector";
import { SVGS } from "../../assets/svgs";
// 
export const Settings = () => {
  const { setOpenedModals } = useStore((s) => ({
    setOpenedModals: s.setOpenedModals,
  }));
  const { t } = useTranslation();
  return (
    <Modal
      minHeight={"80vh"}
      hide={() => setOpenedModals({ action: "remove", name: "settings" })}
    >
      <h1 className="d-flex gap-big align-top justify-center badge bg-gradient">
        {t("settings")}
      </h1>
      <div className="d-flex padding-big">
        <LanguageSelector />
      </div>
      <p>{t("settings-description")}</p>
    </Modal>
  );
};
