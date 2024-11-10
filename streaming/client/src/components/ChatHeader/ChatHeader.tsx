import React, { useEffect, useState } from "react";
import { useStore } from "../../modules/store";
import { SVGS } from "../../assets/svgs";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import { TAgent } from "../../types/agents";
import styles from "./ChatHeader.module.css";
import { Modal } from "../Modal/Modal";
import { SvgButton } from "../SvgButton/SvgButton";
import { updateAgent } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";

export const ChatHeader = ({
  title,
  onTitleEdit,
}: {
  title: string;
  onTitleEdit: (title: string) => void;
}) => {
  const { t } = useTranslation();
  const { toggleSidebar, agents, addAgent, chatState, test } = useStore((state) => ({
    agents: state.agents,
    toggleSidebar: state.toggleSidebar,
    addAgent: state.addAgent,
    chatState: state.chatState,
    test: state.test,
  }));
  const [innerTitle, setInnerTitle] = useState(title);

  const onEdit = (e: React.ChangeEvent<HTMLSpanElement>) => {
    const newTitle = e.target.innerText;

    if (!newTitle || newTitle === innerTitle) return;
    setInnerTitle(newTitle);
    onTitleEdit(newTitle);
  };

  useEffect(() => {
    setInnerTitle(title);
  }, [title]);

  return (
    <div className="chat-header d-flex justify-between">
      <div className="d-flex align-center gap-small">
        {chatState.isSidebarOpened ? (
          <></>
        ) : (
          <SvgButton onClick={toggleSidebar} svg={SVGS.burger} />
        )}

        <FloatingDropdown
          left="0"
          top="100%"
          opener={<SvgButton text={t("agents")} />}
        >
          {agents.map((agent, index) => (
            <AgentComponent key={index} agent={agent} />
          ))}
          <div>
            <SvgButton onClick={addAgent} svg={SVGS.plus} />
          </div>
        </FloatingDropdown>
        <SvgButton onClick={test} text="test" />
      </div>
      <div className="d-flex align-center">
        <span
          contentEditable={true}
          className="text-normal padding-small"
          onBlur={onEdit}
          suppressContentEditableWarning
        >
          {innerTitle}
        </span>
      </div>
    </div>
  );
};

type TAgentComponentProps = {
  agent: TAgent;
};

const AgentComponent = ({ agent }: TAgentComponentProps) => {
  const { toggleAgentSelected, fetchAgents, updateSingleAgent } = useStore(
    (state) => ({
      toggleAgentSelected: state.toggleAgentSelected,
      fetchAgents: state.fetchAgents,
      updateSingleAgent: state.updateSingleAgent,
    })
  );

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
    } catch (e) {}
  };

  return (
    <div className={styles.agentComponent}>
      <section onClick={() => toggleAgentSelected(agent.slug)}>
        <input
          name={`${agent.name}-checkbox`}
          onChange={() => {}}
          type="checkbox"
          checked={agent.selected}
        />
        <span>{agent.name}</span>
      </section>
      <SvgButton svg={SVGS.controls} onClick={showModal} />

      <Modal minHeight={"40vh"} visible={isModalVisible} hide={hideModal}>
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
    model_slug: agent.model_slug || "",
    default: agent.default || false,
    frequency_penalty: agent.frequency_penalty || 0.0,
    max_tokens: agent.max_tokens || 1000,
    presence_penalty: agent.presence_penalty || 0.0,
    act_as: agent.act_as || "",
    system_prompt: agent.system_prompt || "",
    temperature: agent.temperature || 0.7,
    top_p: agent.top_p || 1.0,
  } as TAgent);

  const handleInputChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    const { name, value, type } = e.target;
    // If the name is in temperature, max_tokens, presence_penalty, frequency_penalty, top_p, convert the value to a number
    console.log(type, name, value, "input change");

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

  const save = () => {
    const updatedAgent = {
      ...agent,
      ...formState,
    };
    onSave(updatedAgent);
  };

  const onSubmit = (e) => {
    e.preventDefault();
  };

  const handleDelete = () => {
    removeAgent(agent.slug);
    onDelete();
  };

  return (
    <div>
      <h3>
        {t("configure")} {formState.name}
      </h3>
      <form onSubmit={onSubmit} className="form">
        <label>
          <span>{t("name")}</span>
          <input
            type="text"
            name="name"
            value={formState.name}
            onChange={handleInputChange}
          />
        </label>

        <label>
          <span>{t("slug")}</span>
          <p>{agent.slug}</p>
        </label>

        <label>
          <span>{t("model")}</span>
          <select
            name="model_slug"
            value={formState.model_slug}
            onChange={handleInputChange}
          >
            {models.map((m) => (
              <option key={m.slug} value={m.slug}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("frequency-penalty")}</span>
          <input
            type="range"
            min="-2.0"
            max="2.0"
            step="0.1"
            name="frequency_penalty"
            defaultValue={
              formState.frequency_penalty ? formState.frequency_penalty : 0.0
            }
            onChange={handleInputChange}
          />
          <span>{formState.frequency_penalty}</span>
        </label>
        <label>
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
        <label>
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
        <label>
          <span>{t("act-as")}</span>
          <textarea
            name="act_as"
            value={formState.act_as}
            onChange={handleInputChange}
          />
        </label>
        <label>
          <span>{t("system-prompt")}</span>
          <textarea
            name="system_prompt"
            value={formState.system_prompt}
            onChange={handleInputChange}
          />
        </label>
        <label>
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
        <SvgButton
          extraClass=""
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
          extraClass="bg-danger"
          confirmations={[
            t("sure-this-action-cannot-be-undone-click-again-to-confirm"),
          ]}
        />
      </form>
    </div>
  );
};

export default AgentConfigForm;
