import React, { useState } from "react";
import { useStore } from "../../modules/store";
import { TAgent } from "../../types/agents";
import {
  Modal,
  Button,
  ActionIcon,
  TextInput,
  Textarea,
  NativeSelect,
  Slider,
  Group,
  Stack,
  Text,
  Title,
  Badge,
  Card,
  Checkbox,
  Divider,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { updateAgent, makeAuthenticatedRequest } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import {
  IconSparkles,
  IconPlus,
  IconSettings,
  IconTrash,
  IconDeviceFloppy,
  IconCopy,
  IconExternalLink,
  IconMenu2,
  IconX,
} from "@tabler/icons-react";

export const ChatHeader = ({
  right,
}: {
  right?: React.ReactNode;
}) => {
  const { toggleSidebar, chatState } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    chatState: state.chatState,
  }));

  return (
    <div className="flex items-center justify-between p-2 md:p-4 rounded-none md:rounded-xl w-full shadow-lg z-10 gap-2 md:gap-3 min-w-0" style={{ background: "var(--bg-contrast-color)", border: "1px solid var(--hovered-color)" }}>
      <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
        {!chatState.isSidebarOpened && (
          <ActionIcon
            variant="subtle"
            color="gray"
            size="lg"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            <IconMenu2 size={20} />
          </ActionIcon>
        )}
        <AgentsModal />
      </div>
      <section className="min-w-0 flex-1 md:flex-shrink-0 md:ml-auto overflow-hidden text-right md:text-right">
        {right && right}
      </section>
    </div>
  );
};

type TAgentComponentProps = {
  agent: TAgent;
};

const AgentComponent = ({ agent }: TAgentComponentProps) => {
  const { toggleAgentSelected, updateSingleAgent, chatState, removeAgent, user } =
    useStore((state) => ({
      toggleAgentSelected: state.toggleAgentSelected,
      updateSingleAgent: state.updateSingleAgent,
      chatState: state.chatState,
      removeAgent: state.removeAgent,
      user: state.user,
    }));

  const { t } = useTranslation();
  const [configOpened, { open: openConfig, close: closeConfig }] = useDisclosure(false);
  const canManageAgents = useIsFeatureEnabled("organization-agents-admin");
  const isMultiAgentEnabled = useIsFeatureEnabled("multi-agent-chat");

  const onSave = async (updatedAgent: TAgent) => {
    try {
      await updateAgent(updatedAgent.slug, updatedAgent);
      closeConfig();
      toast.success(t("agent-updated"));
      updateSingleAgent(updatedAgent);
    } catch (e) {
      console.log(e, "error while updating agent");
      toast.error(t("an-error-occurred"));
    }
  };

  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    removeAgent(agent.slug);
    setConfirmDelete(false);
  };

  const isSelected = chatState.selectedAgents.indexOf(agent.slug) !== -1;
  const selectionIndex = chatState.selectedAgents.indexOf(agent.slug);

  // Users can ALWAYS manage their own personal agents (no feature flag needed)
  // Users can manage organization agents ONLY if they have the feature flag
  const isPersonalAgent = agent.organization === null || agent.organization === undefined;
  const isOwnAgent = user && agent.user === user.id;
  const canEditDelete = (isPersonalAgent && isOwnAgent) || (canManageAgents && !isPersonalAgent);

  return (
    <>
      <Card
        shadow="sm"
        padding="sm"
        radius="md"
        withBorder
        w={300}
        style={{
          backgroundColor: isSelected ? "var(--mantine-color-violet-light)" : undefined,
          borderColor: isSelected ? "var(--mantine-color-violet-6)" : undefined,
          cursor: "pointer",
        }}
      >
        <Group
          gap="sm"
          onClick={() => {
            if (isMultiAgentEnabled) {
              toggleAgentSelected(agent.slug);
            } else {
              // Single-agent mode: switch to this agent only
              if (!isSelected) {
                // Deselect all first, then select this one
                chatState.selectedAgents.forEach((s) => toggleAgentSelected(s));
                toggleAgentSelected(agent.slug);
              }
            }
          }}
          wrap="nowrap"
        >
          {isMultiAgentEnabled && (
            <div style={{ position: "relative" }}>
              <Checkbox
                checked={isSelected}
                onChange={() => {}}
                color="violet"
                size="md"
                styles={{
                  input: { cursor: "pointer" },
                }}
              />
              {isSelected && (
                <Badge
                  size="xs"
                  circle
                  color="violet"
                  style={{
                    position: "absolute",
                    top: -6,
                    right: -6,
                    zIndex: 1,
                    pointerEvents: "none",
                  }}
                >
                  {selectionIndex + 1}
                </Badge>
              )}
            </div>
          )}
          <Text fw={500} truncate>
            {agent.name}
          </Text>
        </Group>

        {canEditDelete && (
          <Group gap="xs" mt="sm">
            <Tooltip label={t("settings") || "Settings"}>
              <ActionIcon variant="light" onClick={openConfig}>
                <IconSettings size={18} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={confirmDelete ? t("sure?") : t("delete")}>
              <ActionIcon
                variant="light"
                color={confirmDelete ? "red" : "gray"}
                onClick={handleDelete}
                onMouseLeave={() => setConfirmDelete(false)}
              >
                {confirmDelete ? <IconX size={18} /> : <IconTrash size={18} />}
              </ActionIcon>
            </Tooltip>
          </Group>
        )}
      </Card>

      <Modal
        opened={configOpened}
        onClose={closeConfig}
        title={<Title order={4}>{agent.name}</Title>}
        size="lg"
        centered
        overlayProps={{ backgroundOpacity: 0.55, blur: 3 }}
      >
        <AgentConfigForm agent={agent} onSave={onSave} onDelete={closeConfig} />
      </Modal>
    </>
  );
};

type TAgentConfigProps = {
  agent: TAgent;
  onSave: (agent: TAgent) => void;
  onDelete: () => void;
};

const AgentConfigForm = ({ agent, onSave, onDelete }: TAgentConfigProps) => {
  const { models, removeAgent, user } = useStore((state) => ({
    models: state.models,
    removeAgent: state.removeAgent,
    user: state.user,
  }));

  const { t } = useTranslation();
  const canManageAgents = useIsFeatureEnabled("organization-agents-admin");
  const [confirmDelete, setConfirmDelete] = useState(false);

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
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;

    const floatNames = ["temperature", "frequency_penalty", "presence_penalty", "top_p"];
    const integerNames = ["max_tokens"];
    let newValue: string | number = floatNames.includes(name) ? parseFloat(value) : value;
    if (integerNames.includes(name)) {
      newValue = parseInt(value);
    }
    setFormState((prev) => ({ ...prev, [name]: newValue }));
  };

  const handleLLMChange = (value: string) => {
    const llm = models.find((m) => m.slug === value);
    if (llm) {
      setFormState((prev) => ({
        ...prev,
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
      conversation_title_prompt: formState.conversation_title_prompt?.trim() || undefined,
    };
    onSave(updatedAgent);
  };

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    removeAgent(agent.slug);
    onDelete();
    setConfirmDelete(false);
  };

  const handleCopyMCPConfig = async () => {
    try {
      const response = await makeAuthenticatedRequest<{
        config_json: string;
        agent_name: string;
        instructions: string;
        config_path: string;
      }>("GET", `v1/ai_layers/mcp/${agent.slug}/config/`, {});

      await navigator.clipboard.writeText(response.config_json);

      toast.success(
        `MCP configuration for "${response.agent_name}" copied!\n\n${response.instructions}\n\nPath: ${response.config_path}`,
        {
          duration: 10000,
          style: { whiteSpace: "pre-line", maxWidth: "500px" },
        }
      );
    } catch (error: any) {
      console.error("Error fetching MCP config:", error);
      toast.error(error.response?.data?.error || "Error fetching MCP configuration");
    }
  };

  const voiceOptions = ["shimmer", "alloy", "echo", "fable", "onyx", "nova"].map((v) => ({
    value: v,
    label: v.charAt(0).toUpperCase() + v.slice(1),
  }));

  const modelOptions = models.map((m) => ({
    value: m.slug,
    label: m.name,
  }));

  // Permission check for delete
  const isPersonalAgent = agent.organization === null || agent.organization === undefined;
  const isOwnAgent = user && agent.user === user.id;
  const canEditDelete = (isPersonalAgent && isOwnAgent) || (canManageAgents && !isPersonalAgent);

  return (
    <Stack gap="md">
      <TextInput
        label={t("name")}
        name="name"
        value={formState.name}
        onChange={handleInputChange}
      />

      <NativeSelect
        label={t("model")}
        data={modelOptions}
        value={formState.llm.slug}
        onChange={(e) => {
          const val = e.currentTarget.value;
          handleLLMChange(val);
        }}
      />

      <Group align="flex-end" gap="xs">
        <NativeSelect
          label={t("voice")}
          data={voiceOptions}
          value={formState.openai_voice}
          onChange={(e) => {
            const val = e.currentTarget.value;
            setFormState((prev) => ({ ...prev, openai_voice: val as any }));
          }}
          style={{ flex: 1 }}
        />
        <Tooltip label="OpenAI voice reference">
          <ActionIcon
            variant="light"
            size="lg"
            onClick={() => {
              const url = `https://platform.openai.com/docs/guides/text-to-speech#${formState.openai_voice}`;
              window.open(url, "_blank");
            }}
          >
            <IconExternalLink size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <div>
        <Text size="sm" fw={500} mb={4}>
          {t("frequency-penalty")}: {formState.frequency_penalty}
        </Text>
        <Slider
          min={-2.0}
          max={2.0}
          step={0.1}
          value={formState.frequency_penalty ?? 0}
          onChange={(val) => setFormState((prev) => ({ ...prev, frequency_penalty: val }))}
          marks={[
            { value: -2, label: "-2" },
            { value: 0, label: "0" },
            { value: 2, label: "2" },
          ]}
        />
      </div>

      <div>
        <Text size="sm" fw={500} mb={4}>
          {t("max-tokens")}: {formState.max_tokens}
        </Text>
        <Slider
          min={10}
          max={8000}
          step={10}
          value={formState.max_tokens ?? 4000}
          onChange={(val) => setFormState((prev) => ({ ...prev, max_tokens: val }))}
          marks={[
            { value: 10, label: "10" },
            { value: 4000, label: "4K" },
            { value: 8000, label: "8K" },
          ]}
        />
      </div>

      <div>
        <Text size="sm" fw={500} mb={4}>
          {t("presence-penalty")}: {formState.presence_penalty}
        </Text>
        <Slider
          min={-2.0}
          max={2.0}
          step={0.1}
          value={formState.presence_penalty ?? 0}
          onChange={(val) => setFormState((prev) => ({ ...prev, presence_penalty: val }))}
          marks={[
            { value: -2, label: "-2" },
            { value: 0, label: "0" },
            { value: 2, label: "2" },
          ]}
        />
      </div>

      <Textarea
        label={t("explain-its-role-to-the-ai")}
        placeholder={t("explain-its-role-to-the-ai")}
        value={formState.act_as}
        onChange={(e) => {
          const val = e.currentTarget.value;
          setFormState((prev) => ({ ...prev, act_as: val }));
        }}
        autosize
        minRows={2}
        maxRows={8}
      />

      <Textarea
        label={t("structure-the-ai-system-prompt")}
        value={formState.system_prompt}
        onChange={(e) => {
          const val = e.currentTarget.value;
          setFormState((prev) => ({ ...prev, system_prompt: val }));
        }}
        autosize
        minRows={3}
        maxRows={10}
      />

      <Textarea
        label={t("conversation-title-prompt")}
        placeholder={t("conversation-title-prompt-placeholder")}
        value={formState.conversation_title_prompt || ""}
        onChange={(e) => {
          const val = e.currentTarget.value;
          setFormState((prev) => ({
            ...prev,
            conversation_title_prompt: val,
          }));
        }}
        autosize
        minRows={2}
        maxRows={6}
      />

      <div>
        <Text size="sm" fw={500} mb={4}>
          {t("temperature")}: {formState.temperature}
        </Text>
        <Slider
          min={0}
          max={2.0}
          step={0.1}
          value={formState.temperature}
          onChange={(val) => setFormState((prev) => ({ ...prev, temperature: val }))}
          marks={[
            { value: 0, label: "0" },
            { value: 1, label: "1" },
            { value: 2, label: "2" },
          ]}
        />
      </div>

      <div>
        <Text size="sm" fw={500} mb={4}>
          {t("top-p")}: {formState.top_p}
        </Text>
        <Slider
          min={0.1}
          max={1.0}
          step={0.1}
          value={formState.top_p ?? 1.0}
          onChange={(val) => setFormState((prev) => ({ ...prev, top_p: val }))}
          marks={[
            { value: 0.1, label: "0.1" },
            { value: 0.5, label: "0.5" },
            { value: 1.0, label: "1.0" },
          ]}
        />
      </div>

      <Divider />

      <Button
        variant="light"
        leftSection={<IconCopy size={18} />}
        onClick={handleCopyMCPConfig}
        fullWidth
      >
        Copiar MCP Config
      </Button>

      <Group>
        <Button
          leftSection={<IconDeviceFloppy size={18} />}
          onClick={save}
          variant="light"
        >
          {t("save")}
        </Button>
        {canEditDelete && (
          <Button
            color="red"
            variant={confirmDelete ? "filled" : "light"}
            leftSection={confirmDelete ? <IconX size={18} /> : <IconTrash size={18} />}
            onClick={handleDelete}
            onMouseLeave={() => setConfirmDelete(false)}
          >
            {confirmDelete ? t("sure?") : t("delete")}
          </Button>
        )}
      </Group>
    </Stack>
  );
};

const AgentsModal = () => {
  const { agents, addAgent } = useStore((state) => ({
    agents: state.agents,
    addAgent: state.addAgent,
  }));

  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);

  return (
    <>
      <Button
        variant="light"
        leftSection={<IconSparkles size={18} />}
        onClick={open}
      >
        {t("agents")}
      </Button>

      <Modal
        opened={opened}
        onClose={close}
        title={
          <Group gap="sm">
            <Title order={4}>{t("agents")}</Title>
            <Tooltip label={t("add-an-agent")}>
              <ActionIcon variant="light" onClick={addAgent}>
                <IconPlus size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        }
        size="xl"
        centered
        overlayProps={{ backgroundOpacity: 0.55, blur: 3 }}
      >
        <Group gap="md" justify="center" align="stretch">
          {agents.map((agent) => (
            <AgentComponent key={agent.slug} agent={agent} />
          ))}
        </Group>
      </Modal>
    </>
  );
};

export default AgentConfigForm;
