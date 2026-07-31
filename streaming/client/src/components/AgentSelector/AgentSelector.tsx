import { useStore } from "../../modules/store";
import styles from "./AgentSelector.module.css";
import React, { useEffect, useMemo } from "react";
import { Loader, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";

export const AgentSelector = ({
  selectedSlug,
  onSelectAgent = () => {},
}: {
  selectedSlug?: string;
  onSelectAgent?: (slug: string) => void;
}) => {
  const { t } = useTranslation();
  const { agents, fetchAgents } = useStore((s) => ({
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));

  useEffect(() => {
    if (agents.length === 0) {
      void fetchAgents();
    }
  }, [agents.length, fetchAgents]);

  const value = useMemo(() => {
    if (selectedSlug && agents.some((a) => a.slug === selectedSlug)) {
      return selectedSlug;
    }
    return agents[0]?.slug ?? "";
  }, [agents, selectedSlug]);

  if (agents.length === 0) {
    return (
      <div className={styles.container}>
        <Loader size="sm" color="violet" />
        <Text size="xs" c="dimmed" ml="xs">
          {t("loading")}
        </Text>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <select
        value={value}
        onChange={(e) => {
          onSelectAgent(e.currentTarget.value);
        }}
      >
        {agents.map((a) => (
          <option key={a.id} value={a.slug}>
            {a.name}
          </option>
        ))}
      </select>
    </div>
  );
};
