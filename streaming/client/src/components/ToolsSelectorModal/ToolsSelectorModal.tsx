import React, { useEffect, useState } from "react";
import { Modal, Tabs, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { getAgentToolGroups } from "../../modules/apiCalls";
import type { TMCPToolPresetGroup } from "../../modules/apiCalls";
import { ToolsSelectorContent } from "./ToolsSelectorContent";

export type ToolsSelectorAgent = {
  slug: string;
  name: string;
};

export type ToolsSelectorModalProps = {
  opened: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  agents: ToolsSelectorAgent[];
  valueByAgent: Record<string, string[]>;
  onChange: (slug: string, names: string[]) => void;
  emptyMessage?: string;
};

export function ToolsSelectorModal({
  opened,
  onClose,
  title,
  description,
  agents,
  valueByAgent,
  onChange,
  emptyMessage,
}: ToolsSelectorModalProps) {
  const { t } = useTranslation();
  const [toolGroups, setToolGroups] = useState<TMCPToolPresetGroup[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(
    agents[0]?.slug ?? null
  );
  const showTabs = agents.length > 1;

  useEffect(() => {
    if (!opened) return;
    getAgentToolGroups()
      .then((res) => setToolGroups(res.groups ?? []))
      .catch(() => setToolGroups([]));
  }, [opened]);

  useEffect(() => {
    if (!opened) return;
    if (!agents.some((a) => a.slug === activeTab)) {
      setActiveTab(agents[0]?.slug ?? null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, agents.map((a) => a.slug).join(",")]);

  return (
    <Modal opened={opened} onClose={onClose} title={title} size="lg">
      {agents.length === 0 ? (
        <Text size="sm" c="dimmed">
          {emptyMessage || t("select-at-least-one-agent-to-chat")}
        </Text>
      ) : showTabs ? (
        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            {agents.map((a) => (
              <Tabs.Tab key={a.slug} value={a.slug}>
                {a.name}
              </Tabs.Tab>
            ))}
          </Tabs.List>
          {agents.map((a) => (
            <Tabs.Panel key={a.slug} value={a.slug} pt="sm">
              <ToolsSelectorContent
                key={toolGroups.map((g) => g.group).join(",") || "empty"}
                description={description}
                loadGroups={false}
                toolGroups={toolGroups}
                value={valueByAgent[a.slug] ?? []}
                onChange={(names) => onChange(a.slug, names)}
              />
            </Tabs.Panel>
          ))}
        </Tabs>
      ) : (
        <ToolsSelectorContent
          key={toolGroups.map((g) => g.group).join(",") || "empty"}
          description={description}
          loadGroups={false}
          toolGroups={toolGroups}
          value={valueByAgent[agents[0].slug] ?? []}
          onChange={(names) => onChange(agents[0].slug, names)}
        />
      )}
    </Modal>
  );
}
