import React from "react";
import { Modal } from "../Modal/Modal";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { LanguageSelector } from "../LanguageSelector/LanguageSelector";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

export const Settings = () => {
  const { setOpenedModals } = useStore((s) => ({
    setOpenedModals: s.setOpenedModals,
  }));
  const { t } = useTranslation();

  const menuOptions = [
    {
      name: "General",
      component: (
        <div>
          <div></div>
          <p>{t("settings-description")}</p>
          <LanguageSelector />
        </div>
      ),
      svg: SVGS.controls,
    },
    {
      name: "Appearance",
      component: <div>Appearance</div>,
      svg: SVGS.appearance,
    },
    // {
    //   name: "Notifications",
    //   component: <div className="d-flex padding-big">Notifications</div>,
    // },
    // {
    //   name: "Security",
    //   component: <div className="d-flex padding-big">Security</div>,
    // },
    // {
    //   name: "About",
    //   component: <div className="d-flex padding-big">About</div>,
    // },
  ];

  return (
    <Modal
      minHeight={"80vh"}
      hide={() => setOpenedModals({ action: "remove", name: "settings" })}
    >
      <h1 className="d-flex rounded gap-big align-top justify-center padding-small">
        {t("settings")}
      </h1>

      <Menu options={menuOptions} />
    </Modal>
  );
};

const Menu = ({ options }) => {
  const [selected, setSelected] = React.useState(0);

  return (
    <div className="menu">
      <section className="menu-sidebar">
        {options.map((option, index) => (
          <LabeledButton
            key={index}
            onClick={() => setSelected(index)}
            label={option.name}
            svg={option.svg}
          />
        ))}
      </section>
      <section className="menu-content">{options[selected].component}</section>
    </div>
  );
};

const LabeledButton = ({ label, onClick, svg }) => {
  return (
    <div onClick={onClick} className="labeled-button">
      <SvgButton svg={svg} extraClass="pos-relative w-100" />
      <p className="button-label">{label}</p>
    </div>
  );
};
