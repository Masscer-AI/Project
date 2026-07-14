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
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconCopy, IconPlug, IconPlus, IconTrash } from "@tabler/icons-react";
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

export const McpCredentialsSection = () => {
  const { t } = useTranslation();
  const localizedToolName = useLocalizedToolName();
  const { agents, fetchAgents } = useStore((s) => ({
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));

  const [credentials, setCredentials] = useState<TMCPCredentialSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
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
    void loadCredentials();
    if (agents.length === 0) {
      void fetchAgents();
    }
  }, [loadCredentials, fetchAgents, agents.length]);

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
      await loadCredentials();
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
      await loadCredentials();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } };
      toast.error(err?.response?.data?.error || t("an-error-occurred"));
    }
  };

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Group gap="sm">
            <IconPlug size={24} />
            <Title order={4}>{t("integrations-mcp-title")}</Title>
          </Group>
          <Text size="sm" c="dimmed">
            {t("integrations-mcp-desc")}
          </Text>
        </Stack>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={handleOpenCreate}
        >
          {t("mcp-create-credential")}
        </Button>
      </Group>

      {loading ? (
        <Text size="sm" c="dimmed">…</Text>
      ) : credentials.length === 0 ? (
        <Text size="sm" c="dimmed">{t("mcp-no-credentials")}</Text>
      ) : (
        <Stack gap="xs">
          {credentials.map((cred) => (
            <Card key={cred.id} withBorder padding="sm" radius="md">
              <Group justify="space-between" align="flex-start">
                <Stack gap={2}>
                  <Text size="sm" fw={600}>{cred.name}</Text>
                  <Text size="xs" c="dimmed">{cred.key_prefix}</Text>
                  {cred.allowed_agent_slugs.length > 0 ? (
                    <Group gap={4}>
                      {cred.allowed_agent_slugs.map((slug) => (
                        <Badge key={slug} size="xs" variant="light">{slug}</Badge>
                      ))}
                    </Group>
                  ) : (
                    <Text size="xs" c="dimmed">{t("integrations-mcp-all-agents")}</Text>
                  )}
                  {cred.allowed_tool_names.length > 0 ? (
                    <Group gap={4}>
                      {cred.allowed_tool_names.map((tool) => (
                        <Badge key={tool} size="xs" variant="outline" color="violet">
                          {localizedToolName(tool)}
                        </Badge>
                      ))}
                    </Group>
                  ) : (
                    <Text size="xs" c="dimmed">{t("integrations-mcp-tools-basic-preset")}</Text>
                  )}
                </Stack>
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="subtle"
                    leftSection={<IconCopy size={14} />}
                    onClick={() => void handleCopyConfig(cred.id)}
                  >
                    {t("mcp-copy-cursor-config")}
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
            <Group justify="flex-end">
              <Button variant="default" onClick={closeCreate}>{t("cancel")}</Button>
              <Button loading={submitting} onClick={() => void handleCreate()}>
                {t("mcp-create-credential")}
              </Button>
            </Group>
          </Stack>
        )}
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
