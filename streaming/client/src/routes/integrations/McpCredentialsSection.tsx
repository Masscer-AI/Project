import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Badge,
  Button,
  Card,
  Group,
  Modal,
  MultiSelect,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconCopy,
  IconEye,
  IconPlug,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import {
  createMCPCredential,
  getMCPConnectionConfig,
  listMCPCredentials,
  MCP_TOOL_PRESET_GROUPS,
  revokeMCPCredential,
  TMCPCredentialCreated,
  TMCPCredentialSummary,
} from "../../modules/apiCalls";
import { useStore } from "../../modules/store";
import { useLocalizedToolName } from "../../utils/localizedToolName";

const ALL_TOOL_VALUES = MCP_TOOL_PRESET_GROUPS.flatMap((g) =>
  g.items.map((item) => item.value)
);

type McpCredentialsSectionProps = {
  /** "list" = active connections. "create-advanced" = manual API-key create for Advanced settings. */
  variant?: "list" | "create-advanced";
  onCreated?: () => void;
};

export const McpCredentialsSection = ({
  variant = "list",
  onCreated,
}: McpCredentialsSectionProps) => {
  const { t } = useTranslation();
  const localizedToolName = useLocalizedToolName();
  const { agents, fetchAgents } = useStore((s) => ({
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));

  const [credentials, setCredentials] = useState<TMCPCredentialSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [detailCred, setDetailCred] = useState<TMCPCredentialSummary | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<TMCPCredentialSummary | null>(null);
  const [credentialName, setCredentialName] = useState("");
  const [selectedAgentSlugs, setSelectedAgentSlugs] = useState<string[]>([]);
  const [selectedToolNames, setSelectedToolNames] = useState<string[]>([]);
  const [created, setCreated] = useState<TMCPCredentialCreated | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const conversationalAgents = useMemo(
    () =>
      agents.filter(
        (a) => !a.agent_kind || a.agent_kind === "conversational_agent"
      ),
    [agents]
  );

  const agentOptions = useMemo(
    () =>
      conversationalAgents.map((a) => ({
        value: a.slug,
        label: a.name,
      })),
    [conversationalAgents]
  );

  const allAgentSlugs = useMemo(
    () => conversationalAgents.map((a) => a.slug),
    [conversationalAgents]
  );

  const toolOptions = useMemo(
    () =>
      MCP_TOOL_PRESET_GROUPS.map((group) => ({
        group: t(
          group.group === "Basic"
            ? "integrations-mcp-tools-basic"
            : group.group === "Media"
              ? "integrations-mcp-tools-media"
              : "integrations-mcp-tools-documents"
        ),
        items: group.items.map((item) => ({
          value: item.value,
          label: localizedToolName(item.value),
        })),
      })),
    [t, localizedToolName]
  );

  const loadCredentials = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listMCPCredentials();
      setCredentials(res.credentials || []);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } };
      toast.error(err?.response?.data?.error || t("an-error-occurred"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (variant === "list") {
      void loadCredentials();
    }
    if (agents.length === 0) {
      void fetchAgents();
    }
  }, [loadCredentials, fetchAgents, agents.length, variant]);

  const resetCreateForm = () => {
    setCredentialName("");
    setSelectedAgentSlugs([]);
    setSelectedToolNames([]);
    setCreated(null);
  };

  const handleOpenCreate = () => {
    resetCreateForm();
    openCreate();
  };

  const handleCloseCreate = () => {
    closeCreate();
    resetCreateForm();
    void loadCredentials();
  };

  const handleCreate = async () => {
    const name = credentialName.trim();
    if (!name) {
      toast.error(t("mcp-credential-name"));
      return;
    }
    setSubmitting(true);
    try {
      const payload: {
        name: string;
        allowed_agent_slugs?: string[];
        allowed_tool_names?: string[];
      } = { name };
      if (selectedAgentSlugs.length > 0) {
        payload.allowed_agent_slugs = selectedAgentSlugs;
      }
      if (selectedToolNames.length > 0) {
        payload.allowed_tool_names = selectedToolNames;
      }
      const result = await createMCPCredential(payload);
      setCreated(result);
      toast.success(t("mcp-credential-created"));
      if (variant === "list") {
        await loadCredentials();
      }
      onCreated?.();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } };
      toast.error(err?.response?.data?.error || t("an-error-occurred"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopyConfig = async (credentialId?: string) => {
    try {
      let configText: string;
      if (created) {
        configText = JSON.stringify(created.mcp_config, null, 2);
      } else if (credentialId) {
        const res = await getMCPConnectionConfig(credentialId);
        configText = res.mcp_config_json;
      } else {
        return;
      }
      await navigator.clipboard.writeText(configText);
      toast.success(t("mcp-copy-cursor-config"));
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } };
      toast.error(err?.response?.data?.error || t("an-error-occurred"));
    }
  };

  const handleCopyKey = async () => {
    if (!created?.key) return;
    await navigator.clipboard.writeText(created.key);
    toast.success(t("mcp-copy-key"));
  };

  const handleRevoke = async () => {
    if (!revokeTarget) return;
    try {
      await revokeMCPCredential(revokeTarget.id);
      toast.success(t("mcp-credential-revoked"));
      setRevokeTarget(null);
      setDetailCred(null);
      await loadCredentials();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } };
      toast.error(err?.response?.data?.error || t("an-error-occurred"));
    }
  };

  const toolsSummary = (cred: TMCPCredentialSummary) => {
    if (cred.allowed_tool_names.length === 0) {
      return t("integrations-mcp-tools-basic-preset");
    }
    return t("integrations-mcp-tools-count", {
      count: cred.allowed_tool_names.length,
    });
  };

  const agentsSummary = (cred: TMCPCredentialSummary) => {
    if (cred.allowed_agent_slugs.length === 0) {
      return t("integrations-mcp-all-agents");
    }
    if (cred.allowed_agent_slugs.length === 1) {
      return cred.allowed_agent_slugs[0];
    }
    return t("integrations-mcp-agents-count", {
      count: cred.allowed_agent_slugs.length,
    });
  };

  if (variant === "create-advanced") {
    return (
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start">
          <Stack gap={4}>
            <Group gap="sm">
              <IconPlug size={20} />
              <Title order={5}>{t("mcp-create-credential")}</Title>
            </Group>
            <Text size="sm" c="dimmed">
              {t("integrations-mcp-manual-credential-desc")}
            </Text>
          </Stack>
          <Button
            size="sm"
            leftSection={<IconPlus size={16} />}
            onClick={handleOpenCreate}
          >
            {t("mcp-create-credential")}
          </Button>
        </Group>

        <Modal
          opened={createOpened}
          onClose={handleCloseCreate}
          title={t("mcp-create-credential")}
          size="lg"
        >
          {created ? (
            <Stack gap="sm">
              <Text size="sm" fw={600}>{t("mcp-credential-created")}</Text>
              <TextInput label="MCP URL" value={created.mcp_url} readOnly />
              <Textarea
                label="Bearer token"
                value={created.key}
                readOnly
                autosize
                minRows={2}
              />
              <Group>
                <Button variant="light" leftSection={<IconCopy size={16} />} onClick={() => void handleCopyKey()}>
                  {t("mcp-copy-key")}
                </Button>
                <Button variant="light" leftSection={<IconCopy size={16} />} onClick={() => void handleCopyConfig()}>
                  {t("mcp-copy-cursor-config")}
                </Button>
              </Group>
              <Text size="xs" c="dimmed">{t("mcp-cursor-hint")}</Text>
              <Text size="xs" c="dimmed">
                {created.claude_instructions || t("mcp-claude-hint")}
              </Text>
              <Button onClick={handleCloseCreate}>{t("close")}</Button>
            </Stack>
          ) : (
            <Stack gap="sm">
              <TextInput
                label={t("mcp-credential-name")}
                placeholder={t("mcp-credential-name-placeholder")}
                value={credentialName}
                onChange={(e) => setCredentialName(e.currentTarget.value)}
              />
              <Stack gap={4}>
                <MultiSelect
                  label={t("integrations-mcp-agents-label")}
                  description={t("integrations-mcp-agents-desc")}
                  placeholder={t("integrations-mcp-agents-placeholder")}
                  data={agentOptions}
                  value={selectedAgentSlugs}
                  onChange={setSelectedAgentSlugs}
                  searchable
                  clearable
                />
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="subtle"
                    onClick={() => setSelectedAgentSlugs(allAgentSlugs)}
                  >
                    {t("select-all")}
                  </Button>
                  <Button
                    size="xs"
                    variant="subtle"
                    color="gray"
                    onClick={() => setSelectedAgentSlugs([])}
                  >
                    {t("unselect-all")}
                  </Button>
                </Group>
              </Stack>
              <Stack gap={4}>
                <MultiSelect
                  label={t("integrations-mcp-tools-label")}
                  description={t("integrations-mcp-tools-desc")}
                  placeholder={t("integrations-mcp-tools-placeholder")}
                  data={toolOptions}
                  value={selectedToolNames}
                  onChange={setSelectedToolNames}
                  searchable
                  clearable
                />
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="subtle"
                    onClick={() => setSelectedToolNames([...ALL_TOOL_VALUES])}
                  >
                    {t("select-all")}
                  </Button>
                  <Button
                    size="xs"
                    variant="subtle"
                    color="gray"
                    onClick={() => setSelectedToolNames([])}
                  >
                    {t("unselect-all")}
                  </Button>
                </Group>
              </Stack>
              <Group justify="flex-end">
                <Button variant="default" onClick={closeCreate}>{t("cancel")}</Button>
                <Button loading={submitting} onClick={() => void handleCreate()}>
                  {t("mcp-create-credential")}
                </Button>
              </Group>
            </Stack>
          )}
        </Modal>
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      <Stack gap={4}>
        <Group gap="sm">
          <IconPlug size={24} />
          <Title order={4}>{t("integrations-mcp-title")}</Title>
        </Group>
        <Text size="sm" c="dimmed">
          {t("integrations-mcp-desc")}
        </Text>
      </Stack>

      {loading ? (
        <Text size="sm" c="dimmed">…</Text>
      ) : credentials.length === 0 ? (
        <Text size="sm" c="dimmed">{t("mcp-no-credentials")}</Text>
      ) : (
        <Stack gap="xs">
          {credentials.map((cred) => (
            <Card key={cred.id} withBorder padding="sm" radius="md">
              <Group justify="space-between" align="center" wrap="nowrap">
                <UnstyledButton
                  onClick={() => setDetailCred(cred)}
                  style={{ flex: 1, minWidth: 0, textAlign: "left" }}
                >
                  <Stack gap={4}>
                    <Group gap="xs">
                      <Text size="sm" fw={600}>{cred.name}</Text>
                      {cred.auth_via_oauth ? (
                        <Badge size="xs" variant="light" color="violet">
                          {t("integrations-mcp-oauth-badge")}
                        </Badge>
                      ) : null}
                    </Group>
                    <Text size="xs" c="dimmed">
                      {agentsSummary(cred)} · {toolsSummary(cred)}
                    </Text>
                  </Stack>
                </UnstyledButton>
                <Group gap={4} wrap="nowrap">
                  <Button
                    size="xs"
                    variant="subtle"
                    color="gray"
                    leftSection={<IconEye size={14} />}
                    onClick={() => setDetailCred(cred)}
                  >
                    {t("integrations-mcp-view-details")}
                  </Button>
                  <Button
                    size="xs"
                    variant="subtle"
                    color="red"
                    leftSection={<IconTrash size={14} />}
                    onClick={() => setRevokeTarget(cred)}
                  >
                    {t("mcp-revoke-credential")}
                  </Button>
                </Group>
              </Group>
            </Card>
          ))}
        </Stack>
      )}

      <Modal
        opened={Boolean(detailCred)}
        onClose={() => setDetailCred(null)}
        title={detailCred?.name ?? t("integrations-mcp-credential-details")}
        size="lg"
      >
        {detailCred ? (
          <Stack gap="md">
            <Group gap="xs">
              {detailCred.auth_via_oauth ? (
                <Badge variant="light" color="violet">
                  {t("integrations-mcp-oauth-badge")}
                </Badge>
              ) : (
                <Text size="xs" c="dimmed">{detailCred.key_prefix}</Text>
              )}
            </Group>

            <Stack gap={4}>
              <Text size="sm" fw={600}>{t("integrations-mcp-agents-label")}</Text>
              {detailCred.allowed_agent_slugs.length > 0 ? (
                <Group gap={4}>
                  {detailCred.allowed_agent_slugs.map((slug) => (
                    <Badge key={slug} size="sm" variant="light">{slug}</Badge>
                  ))}
                </Group>
              ) : (
                <Text size="sm" c="dimmed">{t("integrations-mcp-all-agents")}</Text>
              )}
            </Stack>

            <Stack gap={4}>
              <Text size="sm" fw={600}>{t("integrations-mcp-tools-label")}</Text>
              {detailCred.allowed_tool_names.length > 0 ? (
                <Group gap={4}>
                  {detailCred.allowed_tool_names.map((tool) => (
                    <Badge key={tool} size="sm" variant="outline" color="violet">
                      {localizedToolName(tool)}
                    </Badge>
                  ))}
                </Group>
              ) : (
                <Text size="sm" c="dimmed">
                  {t("integrations-mcp-tools-basic-preset")}
                </Text>
              )}
            </Stack>

            <Group justify="flex-end">
              {!detailCred.auth_via_oauth ? (
                <Button
                  variant="light"
                  leftSection={<IconCopy size={16} />}
                  onClick={() => void handleCopyConfig(detailCred.id)}
                >
                  {t("mcp-copy-cursor-config")}
                </Button>
              ) : null}
              <Button
                color="red"
                variant="light"
                leftSection={<IconTrash size={16} />}
                onClick={() => {
                  setRevokeTarget(detailCred);
                }}
              >
                {t("mcp-revoke-credential")}
              </Button>
              <Button variant="default" onClick={() => setDetailCred(null)}>
                {t("close")}
              </Button>
            </Group>
          </Stack>
        ) : null}
      </Modal>

      <Modal
        opened={Boolean(revokeTarget)}
        onClose={() => setRevokeTarget(null)}
        title={t("mcp-revoke-credential")}
      >
        <Stack gap="md">
          <Text size="sm">
            {t("integrations-mcp-revoke-confirm", { name: revokeTarget?.name ?? "" })}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRevokeTarget(null)}>
              {t("cancel")}
            </Button>
            <Button color="red" onClick={() => void handleRevoke()}>
              {t("mcp-revoke-credential")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
};
