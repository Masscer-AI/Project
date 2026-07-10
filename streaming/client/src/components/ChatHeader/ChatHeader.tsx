import React, { useState, useEffect, useRef } from "react";
import { useStore } from "../../modules/store";
import { TAgent } from "../../types/agents";
import {
  Modal,
  Button,
  ActionIcon,
  TextInput,
  Textarea,
  NativeSelect,
  MultiSelect,
  Slider,
  Group,
  Stack,
  Text,
  Title,
  Badge,
  Box,
  Card,
  Checkbox,
  Divider,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { createLLM, deleteLLM, updateAgent, makeAuthenticatedRequest, getUserOrganizations, getOrganizationRoles, getVoices, previewVoice } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import type { TVoiceCatalogEntry } from "../../types/agents";
import {
  formatUnreadNotificationBadge,
  useUnreadNotificationCount,
} from "../../hooks/useUnreadNotificationCount";
import {
  IconSparkles,
  IconPlus,
  IconSettings,
  IconTrash,
  IconDeviceFloppy,
  IconCopy,
  IconMenu2,
  IconPlayerStopFilled,
  IconVolume,
  IconX,
} from "@tabler/icons-react";

export type AgentsModalControls = {
  opened: boolean;
  onOpen: () => void;
  onClose: () => void;
};

export const ChatHeader = ({
  right,
  agentsModal,
}: {
  right?: React.ReactNode;
  agentsModal?: AgentsModalControls;
}) => {
  const { toggleSidebar, chatState } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    chatState: state.chatState,
  }));
  const unreadNotificationCount = useUnreadNotificationCount();

  return (
    <div className="flex items-center justify-between p-2 md:p-4 rounded-none md:rounded-xl w-full shadow-lg z-10 gap-2 md:gap-3 min-w-0" style={{ background: "var(--bg-contrast-color)", border: "1px solid var(--hovered-color)" }}>
      <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
        {!chatState.isSidebarOpened && (
          <Box pos="relative" style={{ display: "inline-block" }}>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="lg"
              onClick={toggleSidebar}
              aria-label="Toggle sidebar"
            >
              <IconMenu2 size={20} />
            </ActionIcon>
            {unreadNotificationCount > 0 && (
              <Badge
                color="red"
                size="sm"
                radius="xl"
                variant="filled"
                pos="absolute"
                top={-4}
                right={-4}
                styles={{ root: { pointerEvents: "none", minWidth: 20 } }}
              >
                {formatUnreadNotificationBadge(unreadNotificationCount)}
              </Badge>
            )}
          </Box>
        )}
        <AgentsModal
          opened={agentsModal?.opened}
          onOpen={agentsModal?.onOpen}
          onClose={agentsModal?.onClose}
        />
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
  const {
    toggleAgentSelected,
    setChatSelectedAgentSlugs,
    updateSingleAgent,
    chatState,
    removeAgent,
    user,
    agents,
  } = useStore((state) => ({
    toggleAgentSelected: state.toggleAgentSelected,
    setChatSelectedAgentSlugs: state.setChatSelectedAgentSlugs,
    updateSingleAgent: state.updateSingleAgent,
    chatState: state.chatState,
    removeAgent: state.removeAgent,
    user: state.user,
    agents: state.agents,
  }));

  const { t } = useTranslation();
  const [configOpened, { open: openConfig, close: closeConfig }] = useDisclosure(false);
  const canManageAgents = useIsFeatureEnabled("edit-organization-agent");
  const isMultiAgentEnabled = useIsFeatureEnabled("multi-agent-chat");

  const onSave = async (updatedAgent: TAgent) => {
    try {
      const saved = await updateAgent(updatedAgent.slug, updatedAgent);
      closeConfig();
      toast.success(t("agent-updated"));
      // Use backend response to keep derived fields (access_mode/allowed_roles) in sync.
      updateSingleAgent(saved as TAgent);
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

  const isPlatformAgent = agent.agent_kind === "platform_assistant";
  const hasPlatformSelected = chatState.selectedAgents.some((slug) => {
    const a = agents.find((x) => x.slug === slug);
    return a?.agent_kind === "platform_assistant";
  });
  // Users can ALWAYS manage their own personal agents (no feature flag needed)
  // Users can manage organization agents ONLY if they have the feature flag
  const isPersonalAgent = agent.organization === null || agent.organization === undefined;
  const isOwnAgent = user && agent.user === user.id;
  const canEditDelete =
    !isPlatformAgent &&
    ((isPersonalAgent && isOwnAgent) || (canManageAgents && !isPersonalAgent));

  const handleAgentSelect = () => {
    if (isPlatformAgent) {
      setChatSelectedAgentSlugs([agent.slug]);
      return;
    }
    if (isMultiAgentEnabled) {
      const hasPlatform = chatState.selectedAgents.some((slug) => {
        const a = useStore.getState().agents.find((x) => x.slug === slug);
        return a?.agent_kind === "platform_assistant";
      });
      if (hasPlatform) {
        setChatSelectedAgentSlugs([agent.slug]);
      } else {
        toggleAgentSelected(agent.slug);
      }
    } else if (!isSelected) {
      setChatSelectedAgentSlugs([agent.slug]);
    }
  };

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
        <Group gap="sm" onClick={handleAgentSelect} wrap="nowrap">
          {isMultiAgentEnabled && !isPlatformAgent && !hasPlatformSelected && (
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
          <Text fw={500} truncate style={{ flex: 1 }}>
            {agent.name}
          </Text>
          {isPlatformAgent && (
            <Badge size="sm" color="violet" variant="light">
              {t("platform-assistant-badge")}
            </Badge>
          )}
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
  const { models, removeAgent, user, fetchAgents } = useStore((state) => ({
    models: state.models,
    removeAgent: state.removeAgent,
    user: state.user,
    fetchAgents: state.fetchAgents,
  }));

  const { t } = useTranslation();
  const canManageAgents = useIsFeatureEnabled("edit-organization-agent");
  const canAddLlm = useIsFeatureEnabled("manage-llm");
  const canSetOwnership = useIsFeatureEnabled("set-agent-ownership");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [addLlmOpened, { open: openAddLlm, close: closeAddLlm }] = useDisclosure(false);
  const [deleteLlmOpened, { open: openDeleteLlm, close: closeDeleteLlm }] = useDisclosure(false);
  const [userOrgs, setUserOrgs] = useState<{ id: string; name: string; is_owner?: boolean }[]>([]);
  const [ownership, setOwnership] = useState<string>(
    agent.organization ? agent.organization : "personal"
  );

  const [accessMode, setAccessMode] = useState<"org_all" | "org_roles">(
    agent.access_mode === "org_roles" ? "org_roles" : "org_all"
  );
  const [orgRoles, setOrgRoles] = useState<{ value: string; label: string }[]>([]);
  const [allowedRoleIds, setAllowedRoleIds] = useState<string[]>(
    (agent.allowed_roles || []).map((r) => r.id)
  );

  // Load user organizations when ownership toggle is available
  useEffect(() => {
    if (!canSetOwnership) return;
    getUserOrganizations()
      .then((orgs) => setUserOrgs(orgs))
      .catch(() => setUserOrgs([]));
  }, [canSetOwnership]);

  useEffect(() => {
    const orgId = ownership !== "personal" ? ownership : agent.organization || null;
    if (!orgId || orgId === "personal") {
      setOrgRoles([]);
      setAllowedRoleIds([]);
      setAccessMode("org_all");
      return;
    }
    getOrganizationRoles(orgId)
      .then((roles) => {
        const opts = (roles || [])
          .filter((r) => r.enabled)
          .map((r) => ({ value: r.id, label: r.name }));
        setOrgRoles(opts);
        // Drop any selected roles that no longer exist
        setAllowedRoleIds((prev) => prev.filter((id) => opts.some((o) => o.value === id)));
      })
      .catch(() => {
        setOrgRoles([]);
      });
  }, [ownership, agent.organization]);

  const [formState, setFormState] = useState({
    name: agent.name || "",
    default_voice_id: agent.default_voice_id ?? null,
    default: agent.default || false,
    max_tokens: agent.max_tokens || 1000,
    act_as: agent.act_as || "",
    system_prompt: agent.system_prompt || "",
    conversation_title_prompt: agent.conversation_title_prompt || "",
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

    const integerNames = ["max_tokens"];
    let newValue: string | number = value;
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

  const [newLlmForm, setNewLlmForm] = useState({
    provider: "",
    name: "",
    slug: "",
  });
  const [isSlugTouched, setIsSlugTouched] = useState(false);

  const toSlug = (value: string) =>
    value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9.\s:_-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-");

  const providerOptions = Array.from(new Set(models.map((m) => m.provider).filter(Boolean))).map(
    (provider) => ({
      value: provider,
      label: provider,
    })
  );

  const handleOpenAddLlm = () => {
    const defaultProvider = providerOptions[0]?.value || "openai";
    setNewLlmForm((prev) => ({
      provider: prev.provider || defaultProvider,
      name: prev.name,
      slug: prev.slug,
    }));
    setIsSlugTouched(false);
    openAddLlm();
  };

  const handleCreateLlm = async () => {
    try {
      const provider = newLlmForm.provider.trim();
      const name = newLlmForm.name.trim();
      const slug = (newLlmForm.slug.trim() || toSlug(name)).trim();

      if (!provider || !name || !slug) {
        toast.error("Provider, name and slug are required");
        return;
      }

      const created = await createLLM({ provider, name, slug });
      await fetchAgents();
      handleLLMChange(created.slug);
      closeAddLlm();
      setNewLlmForm({ provider, name: "", slug: "" });
      setIsSlugTouched(false);
      toast.success(`LLM "${created.name}" created`);
    } catch (error: any) {
      const errMessage = error?.response?.data?.error || "Failed to create LLM";
      toast.error(errMessage);
    }
  };

  const handleDeleteLlm = async () => {
    const slug = formState.llm?.slug;
    if (!slug) return;
    try {
      const result = await deleteLLM(slug);
      await fetchAgents();
      closeDeleteLlm();
      if (result.migrated_to) {
        handleLLMChange(result.migrated_to);
        toast.success(`"${result.deleted}" deleted. ${result.migrated_agents} agent(s) migrated to "${result.migrated_to}".`);
      } else {
        toast.success(`"${result.deleted}" deleted.`);
      }
    } catch (error: any) {
      const errMessage = error?.response?.data?.error || "Failed to delete LLM";
      toast.error(errMessage);
    }
  };

  const save = () => {
    const updatedAgent: TAgent & { ownership?: string; allowed_role_ids?: string[] } = {
      ...agent,
      ...formState,
      conversation_title_prompt: formState.conversation_title_prompt?.trim() || undefined,
    };
    // Include ownership change if the user has the flag
    if (canSetOwnership) {
      updatedAgent.ownership = ownership;
    }
    if (ownership !== "personal" && accessMode === "org_roles") {
      updatedAgent.access_mode = "org_roles";
      updatedAgent.allowed_role_ids = allowedRoleIds;
    } else if (ownership !== "personal") {
      updatedAgent.access_mode = "org_all";
      updatedAgent.allowed_role_ids = [];
    } else {
      updatedAgent.access_mode = "personal";
      updatedAgent.allowed_role_ids = [];
    }
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

  const [voices, setVoices] = useState<TVoiceCatalogEntry[]>([]);
  const [voicePreviewLoading, setVoicePreviewLoading] = useState(false);
  const [voicePreviewPlaying, setVoicePreviewPlaying] = useState(false);
  const voicePreviewAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      voicePreviewAudioRef.current?.pause();
      voicePreviewAudioRef.current = null;
    };
  }, []);

  useEffect(() => {
    getVoices()
      .then((list) => setVoices(list || []))
      .catch(() => setVoices([]));
  }, []);

  const stopVoicePreview = () => {
    const el = voicePreviewAudioRef.current;
    if (el) {
      el.pause();
      el.currentTime = 0;
    }
    setVoicePreviewPlaying(false);
  };

  const handlePlayVoicePreview = async () => {
    const voiceId = formState.default_voice_id;
    if (!voiceId) {
      toast.error(t("select-voice-to-preview"));
      return;
    }
    if (voicePreviewPlaying) {
      stopVoicePreview();
      return;
    }
    setVoicePreviewLoading(true);
    try {
      const { url } = await previewVoice(voiceId);
      stopVoicePreview();
      const audio = new Audio(url);
      voicePreviewAudioRef.current = audio;
      audio.onended = () => setVoicePreviewPlaying(false);
      audio.onerror = () => {
        setVoicePreviewPlaying(false);
        toast.error(t("voice-preview-failed"));
      };
      await audio.play();
      setVoicePreviewPlaying(true);
    } catch (error: any) {
      toast.error(error?.response?.data?.error || t("voice-preview-failed"));
      setVoicePreviewPlaying(false);
    } finally {
      setVoicePreviewLoading(false);
    }
  };

  const voiceOptions = voices.map((v) => ({
    value: v.id,
    label: `${v.name} (${v.provider})`,
  }));

  const modelOptions = models.map((m) => ({
    value: m.slug,
    label: m.name,
  }));

  // Permission check for delete
  const isPlatformAgent = agent.agent_kind === "platform_assistant";
  const isPersonalAgent = agent.organization === null || agent.organization === undefined;
  const isOwnAgent = user && agent.user === user.id;
  const canEditDelete =
    !isPlatformAgent &&
    ((isPersonalAgent && isOwnAgent) || (canManageAgents && !isPersonalAgent));

  return (
    <Stack gap="md">
      <TextInput
        label={t("name")}
        name="name"
        value={formState.name}
        onChange={handleInputChange}
      />

      {canSetOwnership && userOrgs.length > 0 && (
        <NativeSelect
          label={t("ownership")}
          data={[
            { value: "personal", label: t("personal") },
            ...userOrgs.map((org) => ({
              value: org.id,
              label: `${t("organization-agent")}: ${org.name}`,
            })),
          ]}
          value={ownership}
          onChange={(e) => {
            const val = e.currentTarget.value;
            setOwnership(val);
          }}
        />
      )}

      {ownership !== "personal" && (
        <>
          <NativeSelect
            label={t("agent-access") || "Access"}
            data={[
              { value: "org_all", label: t("agent-access-org-all") || "All organization members" },
              { value: "org_roles", label: t("agent-access-org-roles") || "Only specific roles" },
            ]}
            value={accessMode}
            onChange={(e) => {
              const val = e.currentTarget.value as "org_all" | "org_roles";
              setAccessMode(val);
              if (val === "org_all") setAllowedRoleIds([]);
            }}
          />

          {accessMode === "org_roles" && (
            <MultiSelect
              label={t("agent-access-roles") || "Roles with access"}
              data={orgRoles}
              value={allowedRoleIds}
              onChange={setAllowedRoleIds}
              searchable
              nothingFoundMessage={t("no-roles") || "No roles"}
            />
          )}
        </>
      )}

      <Group align="flex-end" gap="xs" wrap="nowrap">
        <NativeSelect
          label={t("model")}
          data={modelOptions}
          value={formState.llm.slug}
          onChange={(e) => {
            const val = e.currentTarget.value;
            handleLLMChange(val);
          }}
          style={{ flex: 1 }}
        />
        {canAddLlm === true && (
          <>
            <Button
              variant="default"
              leftSection={<IconPlus size={16} />}
              onClick={handleOpenAddLlm}
            >
              Add
            </Button>
            <Tooltip label={`Delete "${formState.llm?.name || formState.llm?.slug}"`}>
              <ActionIcon
                variant="subtle"
                color="red"
                size="lg"
                onClick={openDeleteLlm}
              >
                <IconTrash size={18} />
              </ActionIcon>
            </Tooltip>
          </>
        )}
      </Group>

      <Group align="flex-end" gap="xs">
        <NativeSelect
          label={t("voice")}
          data={voiceOptions}
          value={formState.default_voice_id ?? ""}
          onChange={(e) => {
            const val = e.currentTarget.value;
            stopVoicePreview();
            setFormState((prev) => ({
              ...prev,
              default_voice_id: val || null,
            }));
          }}
          disabled={voiceOptions.length === 0}
          style={{ flex: 1 }}
        />
        <Tooltip
          label={
            voicePreviewPlaying
              ? t("stop-voice-preview")
              : t("play-voice-preview")
          }
        >
          <ActionIcon
            variant="light"
            size="lg"
            loading={voicePreviewLoading}
            disabled={!formState.default_voice_id || voiceOptions.length === 0}
            onClick={handlePlayVoicePreview}
            aria-label={
              voicePreviewPlaying
                ? t("stop-voice-preview")
                : t("play-voice-preview")
            }
          >
            {voicePreviewPlaying ? (
              <IconPlayerStopFilled size={18} />
            ) : (
              <IconVolume size={18} />
            )}
          </ActionIcon>
        </Tooltip>
      </Group>

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

      <Modal
        opened={addLlmOpened}
        onClose={closeAddLlm}
        title="Add LLM"
        centered
      >
        <Stack gap="sm">
          <NativeSelect
            label="Provider"
            data={providerOptions}
            value={newLlmForm.provider}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setNewLlmForm((prev) => ({ ...prev, provider: val }));
            }}
          />
          <TextInput
            label="Name"
            value={newLlmForm.name}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setNewLlmForm((prev) => ({
                ...prev,
                name: val,
                slug: isSlugTouched ? prev.slug : toSlug(val),
              }));
            }}
          />
          <TextInput
            label="Slug"
            value={newLlmForm.slug}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setIsSlugTouched(true);
              setNewLlmForm((prev) => ({ ...prev, slug: toSlug(val) }));
            }}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={closeAddLlm}>
              Cancel
            </Button>
            <Button onClick={handleCreateLlm}>Create</Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={deleteLlmOpened}
        onClose={closeDeleteLlm}
        title="Delete LLM"
        centered
        size="sm"
      >
        <Stack gap="sm">
          <Text size="sm">
            Are you sure you want to delete <strong>{formState.llm?.name || formState.llm?.slug}</strong>?
          </Text>
          <Text size="xs" c="dimmed">
            Any agents using this model will be automatically migrated to another model from the same provider.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={closeDeleteLlm}>
              Cancel
            </Button>
            <Button color="red" onClick={handleDeleteLlm}>
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
};

const AgentsModal = ({
  opened: openedProp,
  onOpen: onOpenProp,
  onClose: onCloseProp,
}: {
  opened?: boolean;
  onOpen?: () => void;
  onClose?: () => void;
}) => {
  const { agents, addAgent } = useStore((state) => ({
    agents: state.agents,
    addAgent: state.addAgent,
  }));

  const { t } = useTranslation();
  const [internalOpened, internalHandlers] = useDisclosure(false);
  const isControlled =
    openedProp !== undefined &&
    onOpenProp !== undefined &&
    onCloseProp !== undefined;
  const opened = isControlled ? openedProp : internalOpened;
  const open = isControlled ? onOpenProp! : internalHandlers.open;
  const close = isControlled ? onCloseProp! : internalHandlers.close;
  const canCreateAgents = useIsFeatureEnabled("can-create-agents") === true;

  return (
    <>
      <Button
        variant="light"
        leftSection={<IconSparkles size={18} />}
        onClick={open}
        data-onboarding-target="agents-modal-trigger"
      >
        {t("agents")}
      </Button>

      <Modal
        opened={opened}
        onClose={close}
        title={
          <Group gap="sm">
            <Title order={4}>{t("agents")}</Title>
            {canCreateAgents && (
              <Tooltip label={t("add-an-agent")}>
                <ActionIcon variant="light" onClick={addAgent}>
                  <IconPlus size={18} />
                </ActionIcon>
              </Tooltip>
            )}
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
