import { useStore } from "../../modules/store";
import styles from "./AgentSelector.module.css";
import React, { useState } from "react";

export const AgentSelector = ({
  selectedSlug,
  onSelectAgent = (slug: string) => {},
}: {
  selectedSlug?: string;
  onSelectAgent?: (slug: string) => void;
}) => {
  const { agents } = useStore((s) => ({
    agents: s.agents,
  }));

  const [selectedAgent, setSelectedAgent] = useState(
    selectedSlug ? agents.find((a) => a.slug === selectedSlug) : agents[0]
  );

  const onChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onSelectAgent(e.target.value);
    setSelectedAgent(agents.find((a) => a.slug === e.target.value));
  };

  return (
    <div className={styles.container}>
      <select value={selectedAgent?.slug} onChange={onChange}>
        {agents.map((a) => (
          <option key={a.id} value={a.slug}>
            {a.name}
          </option>
        ))}
      </select>
    </div>
  );
};
