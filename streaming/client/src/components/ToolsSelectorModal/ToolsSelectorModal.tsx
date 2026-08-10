import React, { useEffect, useState } from "react";
import {
  Accordion,
  Button,
  Group,
  Modal,
  Stack,
  Tabs,
  Text,
} from "@mantine/core";
import { useTranslation } from "react-i18next";
import { getAgentToolGroups } from "../../modules/apiCalls";
import type { TMCPToolPresetGroup } from "../../modules/apiCalls";
import { mcpToolGroupLabel } from "../../utils/mcpToolGroupLabel";
import { CapabilitiesChecklist } from "../CapabilitiesChecklist/CapabilitiesChecklist";

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

/**
 * Shared accordion tools picker for chat (session tools) and agent settings
 * (pre-approved tools). Controlled — callers own persistence.
 */
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

  const renderAgentPanel = (agent: ToolsSelectorAgent) => {
    const selected = new Set(valueByAgent[agent.slug] ?? []);
    const allToolNames = toolGroups.flatMap((g) => g.items);
    const allSelected =
      allToolNames.length > 0 &&
      allToolNames.every((name) => selected.has(name));

    return (
      <Stack gap="xs">
        {description ? (
          <Text size="xs" c="dimmed">
            {description}
          </Text>
        ) : null}
        {allToolNames.length > 0 ? (
          <Group justify="flex-end" gap="xs">
            <Button
              size="xs"
              variant="subtle"
              disabled={allSelected}
              onClick={() => onChange(agent.slug, allToolNames)}
            >
              {t("select-all")}
            </Button>
            <Button
              size="xs"
              variant="subtle"
              color="gray"
              onClick={() => onChange(agent.slug, [])}
            >
              {t("unselect-all")}
            </Button>
          </Group>
        ) : null}
        <Accordion multiple defaultValue={toolGroups.map((g) => g.group)}>
          {toolGroups.map((group) => (
            <Accordion.Item key={group.group} value={group.group}>
              <Accordion.Control>
                {mcpToolGroupLabel(group.group, t)}
              </Accordion.Control>
              <Accordion.Panel>
                <CapabilitiesChecklist
                  names={group.items}
                  showBulkActions={false}
                  value={Object.fromEntries(
                    group.items.map((name) => [name, selected.has(name)])
                  )}
                  onChange={(next) => {
                    const nextSelected = new Set(selected);
                    for (const name of group.items) {
                      if (next[name]) nextSelected.add(name);
                      else nextSelected.delete(name);
                    }
                    onChange(agent.slug, Array.from(nextSelected));
                  }}
                />
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      </Stack>
    );
  };

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
              {renderAgentPanel(a)}
            </Tabs.Panel>
          ))}
        </Tabs>
      ) : (
        renderAgentPanel(agents[0])
      )}
    </Modal>
  );
}
