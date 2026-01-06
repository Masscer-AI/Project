import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { SVGS } from "../../assets/svgs";
// import { FloatingDropdown } from "../Dropdown/Dropdown";
import { TAgent } from "../../types/agents";
import { Modal } from "../Modal/Modal";
import { SvgButton } from "../SvgButton/SvgButton";
import { updateAgent } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Textarea } from "../SimpleForm/Textarea";
import { Pill } from "../Pill/Pill";

export const ChatHeader = ({
  // title,
  // onTitleEdit,
  right,
}: {
  // title: string;
  // onTitleEdit: (title: string) => void;
  right?: React.ReactNode;
}) => {
  // const { t } = useTranslation();
  const { toggleSidebar, chatState } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    chatState: state.chatState,
  }));

  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  useEffect(() => {
    // Resetear el estado hover cuando cambia el estado del sidebar
    setHoveredButton(null);
  }, [chatState.isSidebarOpened]);

  return (
    <div className="flex items-center justify-between bg-[#282826] p-4 bg-[#282826] border border-[#282826] rounded-xl w-full shadow-lg z-10 gap-3">
      <div className="flex items-center gap-3">
        {!chatState.isSidebarOpened && (
          <button
            className={`px-4 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
              hoveredButton === 'burger' 
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('burger')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={() => {
              setHoveredButton(null);
              toggleSidebar();
            }}
          >
            <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.burger}</div>
          </button>
        )}
        <AgentsModal />
      </div>
      <section>{right && right}</section>
    </div>
  );
};

type TAgentComponentProps = {
  agent: TAgent;
};

const AgentComponent = ({ agent }: TAgentComponentProps) => {
  const { toggleAgentSelected, updateSingleAgent, chatState, removeAgent } =
    useStore((state) => ({
      toggleAgentSelected: state.toggleAgentSelected,
      updateSingleAgent: state.updateSingleAgent,
      chatState: state.chatState,
      removeAgent: state.removeAgent,
    }));

  const { t } = useTranslation();
  const [isModalVisible, setModalVisible] = useState(false);

  const showModal = () => setModalVisible(true);
  const hideModal = () => setModalVisible(false);

  const onSave = async (agent: TAgent) => {
    try {
      const res = await updateAgent(agent.slug, agent);
      hideModal();
      toast.success(t("agent-updated"));
      updateSingleAgent(agent);
    } catch (e) {
      console.log(e, "error while updating agent");
      toast.error(t("an-error-occurred"));
    }
  };

  const handleDelete = () => {
    removeAgent(agent.slug);
  };

  const isSelected = chatState.selectedAgents.indexOf(agent.slug) !== -1;

  return (
    <div
      className="flex flex-col justify-between p-2.5 items-start w-[300px] border border-gray-500 rounded-[10px] shadow-md"
      style={{
        backgroundColor: isSelected ? "var(--active-color)" : "transparent",
        color: isSelected ? "white" : "var(--font-color)",
      }}
    >
      <section 
        onClick={() => toggleAgentSelected(agent.slug)}
        className="cursor-pointer w-full flex flex-row items-center gap-2.5 rounded-lg p-2.5 transition-colors duration-300"
      >
        <div className="flex gap-2.5 items-center relative">
          <input
            name={`${agent.name}-checkbox`}
            type="checkbox"
            checked={agent.selected}
            onChange={() => {}}
            className="w-6 h-6 appearance-none border border-gray-500 rounded checked:bg-green-500 checked:border-purple-500"
          />
          <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-sm font-bold text-black">
            {chatState.selectedAgents.indexOf(agent.slug) !== -1
              ? chatState.selectedAgents.indexOf(agent.slug) + 1
              : ""}
          </span>
        </div>
        <span>{agent.name}</span>
      </section>
      <section className="flex gap-2.5 w-full">
        <SvgButton
          size="big"
          extraClass={`pressable active-on-hover ${
            isSelected ? "svg-white" : ""
          }`}
          svg={SVGS.controls}
          onClick={showModal}
        />
        <SvgButton
          size="big"
          extraClass={`pressable danger-on-hover ${
            isSelected ? "svg-white text-white" : ""
          }`}
          confirmations={[t("sure?")]}
          svg={SVGS.trash}
          onClick={handleDelete}
        />
      </section>

      <Modal
        minHeight={"40dvh"}
        header={<h3 className="padding-big">{agent.name}</h3>}
        visible={isModalVisible}
        hide={hideModal}
      >
        <AgentConfigForm agent={agent} onSave={onSave} onDelete={hideModal} />
      </Modal>
    </div>
  );
};

type TAgentConfigProps = {
  agent: TAgent;
  onSave: (agent: TAgent) => void;
  onDelete: () => void;
};

const AgentConfigForm = ({ agent, onSave, onDelete }: TAgentConfigProps) => {
  const { models, removeAgent } = useStore((state) => ({
    models: state.models,
    removeAgent: state.removeAgent,
  }));

  const { t } = useTranslation();
  const [formState, setFormState] = useState({
    name: agent.name || "",
    openai_voice: agent.openai_voice || "shimmer",
    default: agent.default || false,
    frequency_penalty: agent.frequency_penalty || 0.0,
    max_tokens: agent.max_tokens || 1000,
    presence_penalty: agent.presence_penalty || 0.0,
    act_as: agent.act_as || "",
    system_prompt: agent.system_prompt || "",
    conversation_title_prompt: agent.conversation_title_prompt || "",
    temperature: agent.temperature || 0.7,
    top_p: agent.top_p || 1.0,
    llm: agent.llm || {
      name: "",
      provider: "",
      slug: "",
    },
  } as TAgent);

  const handleInputChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    const { name, value, type } = e.target;

    const floatNames = [
      "temperature",
      "frequency_penalty",
      "presence_penalty",
      "top_p",
    ];
    const integerNames = ["max_tokens"];
    let newValue = floatNames.includes(name) ? parseFloat(value) : value;
    if (integerNames.includes(name)) {
      newValue = parseInt(value);
    }
    setFormState((prevState) => ({
      ...prevState,
      [name]: newValue,
    }));
  };

  const handleLLMChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const { value } = e.target;
    // Get the LLM from the models array
    const llm = models.find((m) => m.slug === value);

    if (llm) {
      setFormState((prevState) => ({
        ...prevState,
        llm: {
          name: llm.name || "",
          provider: llm.provider || "",
          slug: llm.slug || "",
        },
      }));
    }
  };

  const save = () => {
    const updatedAgent: TAgent = {
      ...agent,
      ...formState,
      // Asegurar que conversation_title_prompt se envíe como null si está vacío
      conversation_title_prompt: formState.conversation_title_prompt?.trim() || undefined,
    };
    onSave(updatedAgent);
  };

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
  };

  const handleDelete = () => {
    removeAgent(agent.slug);
    onDelete();
  };

  const handleSystemPromptChange = (value: string) => {
    setFormState((prevState) => ({
      ...prevState,
      system_prompt: value,
    }));
  };

  const handleConversationTitlePromptChange = (value: string) => {
    setFormState((prevState) => ({
      ...prevState,
      conversation_title_prompt: value,
    }));
  };

  return (
    <form onSubmit={onSubmit}>
      <div className="flex-y gap-medium ">
        <label className="d-flex gap-small align-center">
          <span>{t("name")}:</span>
          <input
            type="text"
            name="name"
            className="input"
            value={formState.name}
            onChange={handleInputChange}
          />
        </label>

        <label className="d-flex gap-small align-center">
          <span>{t("model")}</span>
          <select
            name="llm"
            value={formState.llm.slug}
            onChange={handleLLMChange}
            className="input"
          >
            {models.map((m) => (
              <option key={m.slug} value={m.slug}>
                {m.name}
              </option>
            ))}
          </select>
        </label>

        <label className="d-flex gap-small align-center">
          <span>{t("voice")}</span>
          <select
            name="openai_voice"
            value={formState.openai_voice}
            onChange={handleInputChange}
            className="input"
          >
            {["shimmer", "alloy", "echo", "fable", "onyx", "nova"].map(
              (voice) => (
                <option key={voice} value={voice}>
                  {voice.charAt(0).toUpperCase() + voice.slice(1)}
                </option>
              )
            )}
          </select>
          <Pill
            onClick={() => {
              const url = `https://platform.openai.com/docs/guides/text-to-speech#${formState.openai_voice}`;
              window.open(url, "_blank");
            }}
            extraClass="bg-hovered"
          >
            Ref
          </Pill>
        </label>

        <label className="d-flex gap-small align-center">
          <span>{t("frequency-penalty")}</span>
          <input
            type="range"
            min="-2.0"
            max="2.0"
            step="0.1"
            name="frequency_penalty"
            className="input"
            defaultValue={
              formState.frequency_penalty ? formState.frequency_penalty : 0.0
            }
            onChange={handleInputChange}
          />
          <span>{formState.frequency_penalty}</span>
        </label>
        <label className="d-flex gap-small align-center">
          <span>{t("max-tokens")}</span>
          <input
            type="range"
            min="10"
            max="8000"
            name="max_tokens"
            step="10"
            defaultValue={formState.max_tokens ? formState.max_tokens : 4000}
            onChange={handleInputChange}
          />
          <span>{formState.max_tokens}</span>
        </label>
        <label className="d-flex gap-small align-center">
          <span>{t("presence-penalty")}</span>
          <input
            name="presence_penalty"
            type="range"
            min="-2.0"
            max="2.0"
            step="0.1"
            value={
              formState.presence_penalty ? formState.presence_penalty : 0.0
            }
            onChange={handleInputChange}
          />
          <span>{formState.presence_penalty}</span>
        </label>
        <Textarea
          name="act_as"
          extraClass="my-medium"
          label={t("explain-its-role-to-the-ai")}
          defaultValue={formState.act_as ? formState.act_as : ""}
          onChange={(value) => {
            setFormState((prevState) => ({
              ...prevState,
              act_as: value,
            }));
          }}
          placeholder={t("explain-its-role-to-the-ai")}
        />

        <Textarea
          name="system_prompt"
          extraClass="my-medium"
          label={t("structure-the-ai-system-prompt")}
          defaultValue={formState.system_prompt}
          onChange={handleSystemPromptChange}
        />
        <Textarea
          name="conversation_title_prompt"
          extraClass="my-medium"
          label={t("conversation-title-prompt")}
          defaultValue={formState.conversation_title_prompt || ""}
          onChange={handleConversationTitlePromptChange}
          placeholder={t("conversation-title-prompt-placeholder")}
        />
        <label className="d-flex gap-small align-center">
          <span>{t("temperature")}</span>
          <div>
            <input
              type="range"
              min="0"
              max="2.0"
              step="0.1"
              name="temperature"
              value={formState.temperature}
              onChange={handleInputChange}
            />
            <span>{formState.temperature}</span>
          </div>
        </label>
        <label>
          <span>{t("top-p")}</span>
          <span>
            <input
              name="top_p"
              type="range"
              min="0.1"
              max="1.0"
              step="0.1"
              value={formState.top_p}
              onChange={handleInputChange}
            />
            <span>{formState.top_p}</span>
          </span>
        </label>
      </div>
      <div className="d-flex gap-small mt-small">
        <SvgButton
          extraClass="pressable border-active active-on-hover"
          size="big"
          onClick={save}
          text={t("save")}
          svg={SVGS.download}
        />
        <SvgButton
          size="big"
          onClick={handleDelete}
          text={t("delete")}
          svg={SVGS.close}
          extraClass="border-danger pressable danger-on-hover"
          confirmations={[t("sure?")]}
        />
      </div>
    </form>
  );
};

const AgentsModal = () => {
  const { agents, addAgent, test } = useStore((state) => ({
    agents: state.agents,
    addAgent: state.addAgent,
    test: state.test,
  }));

  const { t } = useTranslation();

  const [isVisible, setVisible] = useState(false);

  const showModal = () => setVisible(true);
  const hideModal = () => setVisible(false);

  return (
    <>
      <SvgButton
        extraClass="pressable active-on-hover hover:!bg-white hover:!text-gray-800 [&>p]:hover:!text-gray-800"
        text={t("agents")}
        onClick={showModal}
        svg={SVGS.stars}
        svgOnHover={SVGS.threeStars}
      />
      {/* <SvgButton
        extraClass="pressable active-on-hover"
        onClick={test}
        svg={SVGS.dumbell}
      /> */}
      <Modal
        extraButtons={
          <SvgButton
            extraClass="pressable active-on-hover padding-medium"
            title={t("add-an-agent")}
            aria-label={t("add-an-agent")}
            onClick={addAgent}
            svg={SVGS.plus}
          />
        }
        header={<h3 className="padding-medium">{t("agents")}</h3>}
        visible={isVisible}
        hide={hideModal}
      >
        <div className="d-flex gap-big wrap-wrap justify-center">
          {agents.map((agent) => (
            <AgentComponent key={agent.slug} agent={agent} />
          ))}
        </div>
      </Modal>
    </>
  );
};

export default AgentConfigForm;
