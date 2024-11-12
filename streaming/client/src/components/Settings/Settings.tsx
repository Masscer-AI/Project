import React, { useEffect } from "react";
import { Modal } from "../Modal/Modal";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { LanguageSelector } from "../LanguageSelector/LanguageSelector";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { getUserOrganizations } from "../../modules/apiCalls";
import { TOrganization } from "../../types";

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
          <h2>General</h2>
          <p>{t("settings-description")}</p>
          <LanguageSelector />
        </div>
      ),
      svg: SVGS.controls,
    },
    {
      name: "Appearance",
      component: (
        <div>
          <h2>Appeareance</h2>
        </div>
      ),
      svg: SVGS.appearance,
    },
    {
      name: "Organization",
      component: <OrganizationManager />,
      svg: SVGS.organization,
    },
    // {
    //   name: "Organization",
    //   component: <OrganizationManager />,
    //   svg: SVGS.organization
    // },
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
      <h2 className="d-flex rounded gap-big align-top justify-center padding-big">
        {t("settings")}
      </h2>

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

const OrganizationManager = () => {
  const { t } = useTranslation();
  const [orgs, setOrgs] = React.useState([] as TOrganization[]);

  useEffect(() => {
    getOrgs();
  }, []);

  const getOrgs = async () => {
    const orgs = await getUserOrganizations();
    setOrgs(orgs);
  };

  return (
    <div>
      <h2>Organization Credentials</h2>
      <p>Here you can manage your organization</p>
      {orgs.length === 0 && <p>{t("no-organizations-message")}</p>}
      {orgs.map((org) => (
        <div key={org.id}>
          <h3>{org.name}</h3>
        </div>
      ))}
    </div>
  );
};

const WhatsappConfig = () => {};
