import React, { useEffect, useState } from "react";
import axios from "axios";
import { useStore } from "../../modules/store";
import { SVGS } from "../../assets/svgs";
import { FloatingDropdown } from "../Dropdown/Dropdown";

export const ChatHeader = () => {
  const {
    toggleSidebar,
    fetchAgents,
    modelsAndAgents,
    toggleAgentSelected
  } = useStore();

  useEffect(() => {
    fetchAgents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const agents = modelsAndAgents.filter(a => a.type === "agent")
  const models = modelsAndAgents.filter(a => a.type === "model")
  return (
    <div className="chat-header">
      <button onClick={toggleSidebar}>{SVGS.burger}</button>
      <FloatingDropdown title={"Models and Agents"}>
        <h3>Agents</h3>
        {agents.map((agent, index) => (
          <label key={index}>
            <input type="checkbox" checked={agent.selected} value={agent.slug} onClick={()=>toggleAgentSelected(agent.slug)} />
            {agent.name}
          </label>
        ))}
        <h3>Models</h3>
        {models.map((modelObj, index) => (
          <label key={index}>
            <input
              type="checkbox"
              value={modelObj.name}
              checked={modelObj.selected}
              onClick={()=>toggleAgentSelected(modelObj.slug)}
            />
            {modelObj.name} ({modelObj.provider})
          </label>
        ))}
      </FloatingDropdown>
    </div>
  );
};
