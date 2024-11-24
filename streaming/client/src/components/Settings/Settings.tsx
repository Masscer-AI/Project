import React, { useEffect } from "react";
import { Modal } from "../Modal/Modal";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { LanguageSelector } from "../LanguageSelector/LanguageSelector";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { getUserOrganizations } from "../../modules/apiCalls";
import { TOrganization } from "../../types";
import { SliderInput } from "../SimpleForm/SliderInput";
import { FloatingDropdown } from "../Dropdown/Dropdown";

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
      component: <AppearanceConfig />,
      svg: SVGS.appearance,
    },
    {
      name: "Organization",
      component: <OrganizationManager />,
      svg: SVGS.organization,
    },
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

export const Menu = ({ options }) => {
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
            selected={index === selected}
          />
        ))}
      </section>
      <section className="menu-content">{options[selected].component}</section>
    </div>
  );
};

const LabeledButton = ({ label, onClick, svg, selected }) => {
  return (
    <div
      onClick={onClick}
      className={`labeled-button ${selected && "active svg-white text-white"}`}
    >
      {/* <SvgButton svg={svg} extraClass="pos-relative w-100" /> */}
      <span>{svg}</span>
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
      <h2>Organization</h2>
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

const AppearanceConfig = () => {
  const { userPreferences, setPreferences } = useStore((s) => ({
    // theme: s.theme,
    // setTheme: s.setTheme,
    userPreferences: s.userPreferences,
    setPreferences: s.setPreferences,
  }));
  const { t } = useTranslation();
  return (
    <div className="flex-y gap-big">
      <h2>{t("appeareance")}</h2>

      <div className="d-flex gap-small flex-y">
        <h4>{t("theme")}</h4>
        <div className="d-flex gap-small align-center">
          <SvgButton
            onClick={() =>
              setPreferences({
                theme: "light",
              })
            }
            extraClass={
              userPreferences.theme === "light"
                ? "bg-active text-white"
                : "bg-hovered"
            }
            text={t("light")}
            svg={SVGS.sun}
          />
          <SvgButton
            onClick={() => setPreferences({ theme: "dark" })}
            extraClass={
              userPreferences.theme === "dark"
                ? "bg-active text-white"
                : "bg-hovered"
            }
            text={t("dark")}
            svg={SVGS.moon}
          />
          <SvgButton
            onClick={() => setPreferences({ theme: "system" })}
            extraClass={
              userPreferences.theme === "system"
                ? "bg-active text-white"
                : "bg-hovered"
            }
            text={t("system")}
            svg={SVGS.pc}
          />
        </div>
      </div>
      <div className="d-flex flex-y gap-small">
        <h4>{t("chat-background-image")}</h4>
        <ImageInput
          onResult={(result) =>
            setPreferences({
              background_image_source: result,
            })
          }
        />
      </div>
    </div>
  );
};

const ImageInput = ({ onResult }) => {
  const handleFileChange = (event) => {
    const file = event.target.files[0];

    if (file) {
      if (!file.type.startsWith("image/")) {
        alert("Please select a valid image file.");
        return;
      }

      const reader = new FileReader();
      reader.onloadend = () => {
        onResult(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  return (
    <div>
      <input
        className="input"
        type="file"
        accept="image/*"
        onChange={handleFileChange}
      />
    </div>
  );
};
