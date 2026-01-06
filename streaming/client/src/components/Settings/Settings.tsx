/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect } from "react";
import { Modal } from "../Modal/Modal";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { LanguageSelector } from "../LanguageSelector/LanguageSelector";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import {
  createOrganization,
  deleteOrganization,
  getOrganizationCredentials,
  getUserOrganizations,
  TOrganizationData,
  updateUser,
  updateOrganization,
  updateOrganizationCredentials,
} from "../../modules/apiCalls";
import { TOrganization } from "../../types";
import { debounce } from "../../modules/utils";
import { toast } from "react-hot-toast";
import { JSONForm } from "../JSONForm/JSONForm";
import mermaid from "mermaid";
import { Textarea } from "../SimpleForm/Textarea";
import { TOrganizationCredentials } from "../../types";

import {
  validateElevenLabsApiKey,
  validateHeyGenApiKey,
} from "../../modules/externalServices";
import { TUserProfile } from "../../types/chatTypes";

const MAX_ALLOWED_ORGANIZATIONS = 1;

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
  const [hoveredButton, setHoveredButton] = React.useState<number | null>(null);

  return (
    <div className="menu">
      <section className="menu-sidebar flex gap-2">
        {options.map((option, index) => (
          <LabeledButton
            key={index}
            onClick={() => setSelected(index)}
            label={option.name}
            svg={option.svg}
            selected={index === selected}
            hovered={hoveredButton === index}
            onMouseEnter={() => setHoveredButton(index)}
            onMouseLeave={() => setHoveredButton(null)}
          />
        ))}
      </section>
      <section className="menu-content">{options[selected].component}</section>
    </div>
  );
};

const LabeledButton = ({ label, onClick, svg, selected, hovered, onMouseEnter, onMouseLeave }) => {
  return (
    <button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 justify-center ${
        hovered || selected
          ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
          : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
      }`}
      style={{ transform: 'none' }}
    >
      <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{svg}</span>
      <span>{label}</span>
    </button>
  );
};

const OrganizationManager = () => {
  const { t } = useTranslation();
  const [orgs, setOrgs] = React.useState([] as TOrganization[]);
  const [showForm, setShowForm] = React.useState(false);
  const [hoveredButton, setHoveredButton] = React.useState<string | null>(null);

  useEffect(() => {
    if (showForm) return;
    getOrgs();
  }, [showForm]);

  const getOrgs = async () => {
    const orgs = await getUserOrganizations();
    console.log(orgs, "USER ORGS");
    setOrgs(orgs);
  };

  return (
    <div className="flex-y gap-medium">
      {showForm ? (
        <OrganizationForm close={() => setShowForm(false)} />
      ) : (
        <>
          {orgs.length === 0 && <p>{t("no-organizations-message")}</p>}
          <div className="d-flex gap-small wrap-wrap justify-center">
            {orgs.map((org) => (
              <OrganizationCard
                reload={getOrgs}
                key={org.id}
                organization={org}
              />
            ))}
          </div>
          {orgs.length < MAX_ALLOWED_ORGANIZATIONS ? (
            <button
              className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
                hoveredButton === 'create-org' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredButton('create-org')}
              onMouseLeave={() => setHoveredButton(null)}
              onClick={() => setShowForm(true)}
            >
              <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.plus}</span>
              <span>{t("create-organization")}</span>
            </button>
          ) : (
            <p>{t("max-organizations-reached")}</p>
          )}
        </>
      )}
    </div>
  );
};

// const WhatsappConfig = () => {};

const MERMAID_THEMES = ["dark", "forest", "neutral", "base", "light"];

const exampleCode = `graph TD; A-->B; A-->C; B-->D; C-->D;`;

const makeThemeCode = (theme: string) => {
  return `%%{init: {'theme':'${theme}'}}%%\n${exampleCode}`;
};

const MermaidExaple = () => {
  const preRef = React.useRef<HTMLPreElement>(null);
  const { theming } = useStore((s) => ({
    theming: s.theming,
  }));

  useEffect(() => {
    mermaid.initialize({ startOnLoad: true, look: "classic" });
  }, []);

  useEffect(() => {
    runMermaid();
  }, [theming.mermaid]);

  const runMermaid = () => {
    // Remove the data-processed attribute
    if (preRef.current) {
      preRef.current.removeAttribute("data-processed");
      mermaid.run();
    }
  };

  return (
    // Add a bigger
    <div className="d-flex justify-center">
      <pre ref={preRef} className="mermaid">
        {makeThemeCode(theming.mermaid)}
      </pre>
    </div>
  );
};

const AppearanceConfig = () => {
  const { userPreferences, setPreferences, theming, setTheming } = useStore(
    (s) => ({
      // theme: s.theme,
      // setTheme: s.setTheme,
      userPreferences: s.userPreferences,
      setPreferences: s.setPreferences,
      theming: s.theming,
      setTheming: s.setTheming,
    })
  );

  const debouncedSetOpacity = debounce((opacity) => {
    setPreferences({ background_image_opacity: opacity });
  }, 1000);
  const { t } = useTranslation();
  const [hoveredTheme, setHoveredTheme] = React.useState<string | null>(null);
  const [hoveredMermaid, setHoveredMermaid] = React.useState<string | null>(null);

  const handleOpacityChange = (event) => {
    const opacity = parseFloat(event.target.value);
    debouncedSetOpacity(opacity);
  };

  return (
    <div className="flex-y gap-big">
      {/* <h2>{t("appeareance")}</h2> */}

      <div className="d-flex gap-small flex-y">
        <h4>{t("theme")}</h4>
        <div className="d-flex gap-2 align-center flex-wrap">
          <button
            className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 ${
              hoveredTheme === 'light' || userPreferences.theme === "light"
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredTheme('light')}
            onMouseLeave={() => setHoveredTheme(null)}
            onClick={() => setPreferences({ theme: "light" })}
          >
            <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.sun}</span>
            <span>{t("light")}</span>
          </button>
          <button
            className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 ${
              hoveredTheme === 'dark' || userPreferences.theme === "dark"
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredTheme('dark')}
            onMouseLeave={() => setHoveredTheme(null)}
            onClick={() => setPreferences({ theme: "dark" })}
          >
            <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.moon}</span>
            <span>{t("dark")}</span>
          </button>
          <button
            className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 ${
              hoveredTheme === 'system' || userPreferences.theme === "system"
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredTheme('system')}
            onMouseLeave={() => setHoveredTheme(null)}
            onClick={() => setPreferences({ theme: "system" })}
          >
            <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.pc}</span>
            <span>{t("system")}</span>
          </button>
        </div>
      </div>
      <hr className="separator my-medium" />
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
      <hr className="separator my-medium" />
      <div className="flex-y gap-small ">
        <h4>{t("mermaid-theme")}</h4>
        <p>{t("mermaid-theme-description")}</p>
        <div className="d-flex gap-2 flex-wrap">
          {MERMAID_THEMES.map((theme) => (
            <button
              key={theme}
              className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 ${
                hoveredMermaid === theme || theming.mermaid === theme
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredMermaid(theme)}
              onMouseLeave={() => setHoveredMermaid(null)}
              // @ts-ignore
              onClick={() => setTheming({ mermaid: theme as any })}
            >
              <span>{theme.charAt(0).toUpperCase() + theme.slice(1)}</span>
            </button>
          ))}
        </div>
        <MermaidExaple />
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
  const [hoveredButton, setHoveredButton] = React.useState<string | null>(null);

  const handleUpdateUser = async () => {
    const tid = toast.loading(t("updating-user"));
    try {
      await updateUser({
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
      <button
        className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
          hoveredButton === 'save' 
            ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
            : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
        }`}
        style={{ transform: 'none' }}
        onMouseEnter={() => setHoveredButton('save')}
        onMouseLeave={() => setHoveredButton(null)}
        onClick={handleUpdateUser}
      >
        <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.save}</span>
        <span>{t("save")}</span>
      </button>
    </div>
  );
};

const UserConfig = () => {
  const { t } = useTranslation();

  const { user, setUser } = useStore((s) => ({
    user: s.user,
    setUser: s.setUser,
  }));

  const [profile, setProfile] = React.useState(
    user?.profile || ({} as TUserProfile)
  );

  const handleUpdateUser = async (data) => {
    console.log(data);

    if (!user) return;

    try {
      await updateUser({
        username: user.username,
        email: user.email,
        profile,
      });
      toast.success(t("user-updated"));
      // @ts-ignore
      setUser(newUser);
    } catch (e) {
      toast.error(t(e.response.data.error));
    }
  };

  const onKeyChange = async (key, value) => {
    const newProfile = { ...profile };
    newProfile[key] = value;
    setProfile(newProfile);
  };

  return (
    <div className="flex-y gap-big">
      {/* <pre>{JSON.stringify(user, null, 2)}</pre> */}

      <JSONForm
        data={user?.profile || {}}
        onSubmit={handleUpdateUser}
        submitText={t("save-profile")}
        onKeyChange={onKeyChange}
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

const OrganizationForm = ({ close }: { close: () => void }) => {
  const { t } = useTranslation();

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.target as HTMLFormElement);
    const data = Object.fromEntries(formData.entries());
    const response = await createOrganization(data as TOrganizationData);
    console.log(response);
    close();
  };

  return (
    <div>
      <form className="flex-y gap-medium" onSubmit={handleSubmit}>
        <h3 className="text-center">{t("create-organization")}</h3>
        <label htmlFor="name">
          {t("choose-the-name-of-your-organization")}
        </label>
        <input
          type="text"
          name="name"
          className="input"
          placeholder={t("name-for-your-organization")}
        />
        <label htmlFor="description">{t("describe-your-organization")}</label>
        <Textarea
          name="description"
          placeholder={t("describe-your-organization")}
          // onChange={(e) => {}}
          defaultValue={""}
        />
        <div className="d-flex gap-small">
          <SvgButton
            text={t("cancel")}
            svg={SVGS.close}
            extraClass="w-100 pressable danger-on-hover"
            onClick={close}
          />
          <SvgButton
            text={t("create")}
            type="submit"
            svg={SVGS.save}
            extraClass="w-100 pressable active-on-hover"
          />
        </div>
      </form>
    </div>
  );
};

const OrganizationCard = ({
  reload,
  organization,
}: {
  reload: () => void;
  organization: TOrganization;
}) => {
  const { t } = useTranslation();

  const handleDelete = async () => {
    const response = await deleteOrganization(organization.id);
    console.log(response);
    toast.success(t("organization-deleted"));
    reload();
  };

  const [hoveredButton, setHoveredButton] = React.useState<string | null>(null);

  return (
    <div className="bg-black/95 backdrop-blur-md border border-gray-700 rounded-2xl p-6 flex flex-col gap-4 shadow-lg">
      <h3 className="text-center text-white font-bold">{organization.name}</h3>
      {organization.description && (
        <p className="text-center text-gray-300">{organization.description}</p>
      )}
      <div className="d-flex gap-3 justify-center">
        <button
          className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 ${
            hoveredButton === 'delete' 
              ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
              : 'bg-[#dc2626] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#b91c1c]'
          }`}
          style={{ transform: 'none' }}
          onMouseEnter={() => setHoveredButton('delete')}
          onMouseLeave={() => setHoveredButton(null)}
          onClick={() => {
            if (window.confirm(t("sure-this-action-is-irreversible"))) {
              handleDelete();
            }
          }}
        >
          <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.trash}</span>
        </button>
        <OrganizationConfigModal organization={organization} />
      </div>
    </div>
  );
};

const OrganizationConfigModal = ({
  organization,
}: {
  organization: TOrganization;
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = React.useState(false);
  const [innerOrganization, setInnerOrganization] =
    React.useState(organization);
  const [hoveredButton, setHoveredButton] = React.useState<string | null>(null);

  const [credentials, setCredentials] = React.useState(
    null as TOrganizationCredentials | null
  );

  useEffect(() => {
    if (!isOpen) return;
    getCredentials();
  }, [organization, isOpen]);

  const getCredentials = async () => {
    const response = await getOrganizationCredentials(organization.id);
    setCredentials(response);
  };

  const handleUpdateCredentials = async (key: string, value: string) => {
    if (!credentials) return;

    if (key === "elevenlabs_api_key") {
      const isValid = await validateElevenLabsApiKey(value);
      if (!isValid) {
        toast.error(t("invalid-api-key"));
        return;
      } else {
        toast.success(t("valid-api-key"));
      }
    }

    if (key === "heygen_api_key") {
      const isValid = await validateHeyGenApiKey(value);
      if (!isValid) {
        toast.error(t("invalid-api-key"));
        return;
      } else {
        toast.success(t("valid-api-key"));
      }
    }
    setCredentials({
      ...credentials,
      [key]: value,
    });
  };

  const handleSave = async () => {
    await updateOrganization(organization.id, innerOrganization);
    if (!credentials) return;

    await updateOrganizationCredentials(organization.id, credentials);

    toast.success(t("organization-updated"));
    setIsOpen(false);
  };

  const [hoveredEdit, setHoveredEdit] = React.useState(false);

  return (
    <>
      <button
        className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 ${
          hoveredEdit 
            ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
            : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
        }`}
        style={{ transform: 'none' }}
        onMouseEnter={() => setHoveredEdit(true)}
        onMouseLeave={() => setHoveredEdit(false)}
        onClick={() => setIsOpen(true)}
      >
        <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.edit}</span>
      </button>
      <Modal
        visible={isOpen}
        hide={() => setIsOpen(false)}
        header={
          <h3 className="text-center padding-medium">
            {t("organization-config")}
          </h3>
        }
      >
        <div className="flex-y gap-medium">
          <h5>{t("organization-name")}</h5>
          <input
            type="text"
            name="name"
            className="input"
            defaultValue={innerOrganization.name}
            onChange={(e) => {
              setInnerOrganization({
                ...innerOrganization,
                name: e.target.value,
              });
            }}
          />
          <h5>{t("describe-your-organization")}</h5>
          <Textarea
            name="description"
            defaultValue={innerOrganization.description}
            onChange={(value) => {
              setInnerOrganization({
                ...innerOrganization,
                description: value,
              });
            }}
          />
          <h5>{t("api-keys")}</h5>
          <p className="text-secondary">{t("api-keys-description")}</p>
          <JSONForm
            data={credentials || {}}
            onKeyChange={handleUpdateCredentials}
            fieldMapping={{
              elevenlabs_api_key: {
                type: "string",
                label: t("elevenlabs_api_key"),
              },
              heygen_api_key: { type: "string", label: t("heygen_api_key") },
            }}
            hiddenKeys={[
              "id",
              "organization",
              "created_at",
              "updated_at",
              "openai_api_key",
              "brave_api_key",
              "anthropic_api_key",
              "pexels_api_key",
            ]}
          />
          <button
            className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
              hoveredButton === 'save' 
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('save')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={handleSave}
          >
            <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.save}</span>
            <span>{t("save")}</span>
          </button>
        </div>
      </Modal>
    </>
  );
};
