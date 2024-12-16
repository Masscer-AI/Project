import React, { useEffect } from "react";
import { Modal } from "../Modal/Modal";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { LanguageSelector } from "../LanguageSelector/LanguageSelector";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { getUserOrganizations, updateUser } from "../../modules/apiCalls";
import { TOrganization } from "../../types";
import { debounce } from "../../modules/utils";
import { toast } from "react-hot-toast";
import { JSONForm } from "../JSONForm/JSONForm";

export const Settings = () => {
  const { setOpenedModals } = useStore((s) => ({
    setOpenedModals: s.setOpenedModals,
  }));
  const { t } = useTranslation();

  const menuOptions = [
    {
      name: t("general"),
      component: <GeneralConfig />,
      svg: SVGS.controls,
    },
    {
      name: t("appearance"),
      component: <AppearanceConfig />,
      svg: SVGS.appearance,
    },
    {
      name: t("organization"),
      component: <OrganizationManager />,
      svg: SVGS.organization,
    },
    {
      name: t("user"),
      component: <UserConfig />,
      svg: SVGS.person,
    },
  ];

  return (
    <Modal
      minHeight={"80vh"}
      header={<h3 className="padding-big">{t("settings")}</h3>}
      hide={() => setOpenedModals({ action: "remove", name: "settings" })}
    >
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
      {/* <h2>{t("organization")}</h2> */}
      <p>{t("organization-description")}</p>
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

  const debouncedSetOpacity = debounce((opacity) => {
    setPreferences({ background_image_opacity: opacity });
  }, 1000);
  const { t } = useTranslation();

  const handleOpacityChange = (event) => {
    const opacity = parseFloat(event.target.value);
    debouncedSetOpacity(opacity);
  };

  return (
    <div className="flex-y gap-big">
      {/* <h2>{t("appeareance")}</h2> */}

      <div className="d-flex gap-small flex-y">
        <h4>{t("theme")}</h4>
        <div className="d-flex gap-small align-center">
          <SvgButton
            onClick={() =>
              setPreferences({
                theme: "light",
              })
            }
            extraClass={`pressable active-on-hover ${userPreferences.theme === "light" ? "bg-active svg-white" : "bg-hovered"}`}
            text={t("light")}
            svg={SVGS.sun}
          />
          <SvgButton
            onClick={() => setPreferences({ theme: "dark" })}
            extraClass={`pressable active-on-hover ${userPreferences.theme === "dark" ? "bg-active svg-white" : "bg-hovered "}`}
            text={t("dark")}
            svg={SVGS.moon}
          />
          <SvgButton
            onClick={() => setPreferences({ theme: "system" })}
            extraClass={`pressable active-on-hover ${userPreferences.theme === "system" ? "bg-active svg-white" : "bg-hovered"}`}
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
        <h4>{t("opacity-chat-background-image")}</h4>
        <input
          onChange={handleOpacityChange}
          title={t("opacity")}
          defaultValue={userPreferences.background_image_opacity}
          type="range"
          min="0"
          max="1"
          step="0.01"
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

const GeneralConfig = () => {
  const { t } = useTranslation();

  const { user, setUser } = useStore((s) => ({
    user: s.user,
    setUser: s.setUser,
  }));

  const [username, setUsername] = React.useState(user?.username || "");
  const [email, setEmail] = React.useState(user?.email || "");
  const [error, setError] = React.useState("");

  const handleUpdateUser = async () => {
    const tid = toast.loading(t("updating-user"));
    try {
      const response = await updateUser({
        username,
        email,
        profile: user?.profile,
      });
      toast.success(t("user-updated"));
      setUser({ ...user, username, email });
      setError("");
    } catch (e) {
      toast.error(t(e.response.data.error));
      setError(t(e.response.data.error));
    } finally {
      toast.dismiss(tid);
    }
  };
  return (
    <div className="flex-y gap-small">
      <p>{t("settings-description")}</p>
      <LanguageSelector />
      <hr className="separator my-medium" />
      <div className="d-flex gap-small align-center">
        <h4>{t("username")}</h4>
        <input
          name="username"
          type="text"
          value={username}
          className="input"
          onChange={(e) => setUsername(e.target.value)}
        />
      </div>
      <div className="d-flex gap-small align-center">
        <h4>{t("email")}</h4>
        <input
          name="email"
          type="email"
          value={email}
          className="input w-100"
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      {error && <p className="error text-danger">{error}</p>}
      <SvgButton
        text={t("save")}
        svg={SVGS.save}
        onClick={handleUpdateUser}
        size="big"
        extraClass="active-on-hover pressable"
      />
    </div>
  );
};

const UserConfig = () => {
  const { t } = useTranslation();

  const { user, setUser } = useStore((s) => ({
    user: s.user,
    setUser: s.setUser,
  }));

  const handleUpdateUser = async (data) => {
    console.log(data);
  };

  const onKeyChange = async (key, value) => {
    if (!user) return;
    const newUser = { ...user };
    const profile = newUser.profile || {
      id: "",
      avatar_url: "",
      bio: "",
      sex: "",
      age: 0,
      birthday: "",
      name: "",
    };
    profile[key] = value;

    newUser.profile = profile;

    try {
      await updateUser({
        username: newUser.username,
        email: newUser.email,
        profile,
      });
      toast.success(t("user-updated"));
      // @ts-ignore
      setUser(newUser);
    } catch (e) {
      toast.error(t(e.response.data.error));
    }
  };

  const onKeyChangeDebounced = debounce(onKeyChange, 1000);

  return (
    <div className="flex-y gap-big">
      {/* <pre>{JSON.stringify(user, null, 2)}</pre> */}

      <JSONForm
        data={user?.profile || {}}
        onSubmit={handleUpdateUser}
        onKeyChange={onKeyChangeDebounced}
        hiddenKeys={[
          "id",
          "user",
          "created_at",
          "updated_at",
          "age",
          "avatar_url",
        ]}
        fieldMapping={{
          name: { type: "string", label: t("name") },
          birthday: { type: "date", label: t("birthday") },
          bio: { type: "textarea", label: t("bio") },
          sex: { type: "string", label: t("sex") },
          avatar_url: { type: "image", label: t("avatar") },
        }}
      />
      <p className="text-small text-secondary">
        {t("why-user-info-matters-for-ai-personalization")}
      </p>
    </div>
  );
};
