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
export const ChatHeader = () => {
  const { toggleSidebar, fetchAgents, agents, addAgent } = useStore(
    (state) => ({
      agents: state.agents,
      toggleSidebar: state.toggleSidebar,
      fetchAgents: state.fetchAgents,
      addAgent: state.addAgent,
    })
  );

  useEffect(() => {
    fetchAgents();
  }, []);

  return (
    <div className="chat-header">
      <button className="button" onClick={toggleSidebar}>
        {SVGS.burger}
      </button>
      <FloatingDropdown
        left="0"
        top="100%"
        opener={<button className="button">Agents</button>}
      >
        {agents.map((agent, index) => (
          <AgentComponent key={index} agent={agent} />
        ))}
        <div>
          <SvgButton onClick={addAgent} svg={SVGS.plus} />
        </div>
      </FloatingDropdown>
    </div>
  );
};

type TAgentComponentProps = {
  agent: TAgent;
};

const AgentComponent = ({ agent }: TAgentComponentProps) => {
  const { toggleAgentSelected, fetchAgents } = useStore((state) => ({
    toggleAgentSelected: state.toggleAgentSelected,
    fetchAgents: state.fetchAgents,
  }));

  const [isModalVisible, setModalVisible] = useState(false);

  const showModal = () => setModalVisible(true);
  const hideModal = () => setModalVisible(false);

  const onSave = async (agent: TAgent) => {
    try {
      const res = await updateAgent(agent.slug, agent);
      hideModal();
      toast.success("Agent updated in DB!");
      fetchAgents();
    } catch (e) {
      console.log("ERROR TRYING TO SAVE AGENT", e);
    }
  };

  return (
    <div className={styles.agentComponent}>
      <section onClick={() => toggleAgentSelected(agent.slug)}>
        <input onChange={() => {}} type="checkbox" checked={agent.selected} />
        <span>{agent.name}</span>
      </section>
      <SvgButton svg={SVGS.controls} onClick={showModal} />

      <Modal visible={isModalVisible} hide={hideModal}>
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
  });

  const handleInputChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    const { name, value, type } = e.target;
    setFormState((prevState) => ({
      ...prevState,
      [name]: value,
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
      <h3>Configure {formState.name}</h3>
      <form onSubmit={onSubmit} className="form">
        <label>
          <span>Name</span>
          <input
            type="text"
            name="name"
            value={formState.name}
            onChange={handleInputChange}
          />
        </label>

        <label>
          <span>Slug</span>
          <p>{agent.slug}</p>
        </label>

        <label>
          <span>Model:</span>
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
          <span>Frequency Penalty:</span>
          <input
            type="range"
            min="-2.0"
            max="2.0"
            step="0.1"
            name="frequency_penalty"
            value={formState.frequency_penalty}
            onChange={handleInputChange}
          />
          <span>{formState.frequency_penalty}</span>
        </label>
        <label>
          <span>Max Tokens:</span>
          <input
            type="range"
            min="10"
            max="16000"
            name="max_tokens"
            step="10"
            value={formState.max_tokens}
            onChange={handleInputChange}
          />
          <span>{formState.max_tokens}</span>
        </label>
        <label>
          <span>Presence Penalty:</span>
          <input
            name="presence_penalty"
            type="range"
            min="-2.0"
            max="2.0"
            step="0.1"
            value={formState.presence_penalty}
            onChange={handleInputChange}
          />
          <span>{formState.presence_penalty}</span>
        </label>
        <label>
          <span>Act as:</span>
          <textarea
            name="act_as"
            value={formState.act_as}
            onChange={handleInputChange}
          />
        </label>
        <label>
          <span>System Prompt:</span>
          <textarea
            name="system_prompt"
            value={formState.system_prompt}
            onChange={handleInputChange}
          />
        </label>
        <label>
          <span>Temperature:</span>
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
          <span>Top P:</span>
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
          text="Save"
          svg={SVGS.download}
        />
        <SvgButton
          size="big"
          onClick={handleDelete}
          text="Delete"
          svg={SVGS.close}
          extraClass="bg-danger"
          confirmations={[
            "Sure? This action cannot be undone. Click again to confirm.",
          ]}
        />
      </form>
    </div>
  );
};

export default AgentConfigForm;
