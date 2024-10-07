import React, { useEffect } from "react";
import axios from "axios";
import { useStore } from "../../modules/store";
import { SVGS } from "../../assets/svgs";
import { Link } from "react-router-dom"

export const ChatHeader = () => {
  const {
    setModels,
    models,
    model,
    setModel,
    toggleSidebar,
    agents,
    fetchAgents,
  } = useStore();

  useEffect(() => {
    getModels();
    fetchAgents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getModels = async () => {
    try {
      const response = await axios.get("/get-models");
      const ollamaModels = response.data.map((model) => ({
        name: model.name,
        provider: "ollama",
      }));
      setModels([...models, ...ollamaModels]);
    } catch (e) {
      console.error(e);
      
    }
  };

  return (
    <div className="chat-header">
      <button onClick={toggleSidebar}>{SVGS.burger}</button>
      <select
        value={model.name}
        onChange={(e) => {
          const selectedModel = models.find((m) => m.name === e.target.value);
          if (selectedModel) {
            setModel(selectedModel);
          }
        }}
      >
        {models.map((modelObj, index) => (
          <option key={index} value={modelObj.name}>
            {modelObj.name} ({modelObj.provider})
          </option>
        ))}
      </select>
      <select>
        {agents.map((agent, index) => (
          <option key={index} value={agent.slug}>
            {agent.name}
          </option>
        ))}
      </select>
      {/* <button><Link to={"/tools"}>Gallo click acá: {SVGS.controls}</Link></button> */}
    </div>
  );
};
