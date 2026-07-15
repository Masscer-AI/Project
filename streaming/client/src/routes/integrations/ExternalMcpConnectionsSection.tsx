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
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconCloud, IconPlus, IconTrash } from "@tabler/icons-react";
import {
  createMCPExternalConnection,
  listMCPExternalCatalog,
  listMCPExternalConnections,
  revokeMCPExternalConnection,
  TMCPExternalCatalogEntry,
  TMCPExternalConnectionSummary,
} from "../../modules/apiCalls";
import { useStore } from "../../modules/store";
import { useLocalizedExternalMcpToolName } from "../../utils/localizedToolName";

export const ExternalMcpConnectionsSection = () => {
  const { t } = useTranslation();
  const localizedExternalTool = useLocalizedExternalMcpToolName();
  const { agents, fetchAgents } = useStore((s) => ({
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));

  const [catalog, setCatalog] = useState<TMCPExternalCatalogEntry[]>([]);
  const [connections, setConnections] = useState<TMCPExternalConnectionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [revokeTarget, setRevokeTarget] = useState<TMCPExternalConnectionSummary | null>(null);
  const [connectionName, setConnectionName] = useState("");
  const [selectedCatalogKey, setSelectedCatalogKey] = useState<string | null>(null);
  const [selectedAgentSlugs, setSelectedAgentSlugs] = useState<string[]>([]);
  const [selectedRemoteTools, setSelectedRemoteTools] = useState<string[]>([]);
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

  const selectedCatalog = useMemo(
    () => catalog.find((c) => c.key === selectedCatalogKey) ?? null,
    [catalog, selectedCatalogKey]
  );

  const remoteToolOptions = useMemo(() => {
    if (!selectedCatalog) return [];
    return selectedCatalog.default_remote_tool_names.map((tool) => ({
      value: tool,
      label: localizedExternalTool(selectedCatalog.key, tool),
    }));
  }, [selectedCatalog, localizedExternalTool]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [catalogRes, connectionsRes] = await Promise.all([
        listMCPExternalCatalog(),
        listMCPExternalConnections(),
      ]);
      setCatalog(catalogRes.catalog || []);
      setConnections(connectionsRes.connections || []);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } };
      toast.error(err?.response?.data?.error || t("an-error-occurred"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadData();
    if (agents.length === 0) {
      void fetchAgents();
    }
  }, [loadData, fetchAgents, agents.length]);

  useEffect(() => {
    if (catalog.length > 0 && !selectedCatalogKey) {
      setSelectedCatalogKey(catalog[0].key);
    }
  }, [catalog, selectedCatalogKey]);

  const resetCreateForm = () => {
    setConnectionName("");
    setSelectedCatalogKey(catalog[0]?.key ?? null);
    setSelectedAgentSlugs([]);
    setSelectedRemoteTools([]);
  };

  const handleOpenCreate = () => {
    resetCreateForm();
    openCreate();
  };

  const handleCloseCreate = () => {
    closeCreate();
    resetCreateForm();
    void loadData();
  };

  const handleCreate = async () => {
    const name = connectionName.trim();
    if (!name) {
      toast.error(t("integrations-external-mcp-name"));
      return;
    }
    if (!selectedCatalogKey) {
      toast.error(t("integrations-external-mcp-catalog-required"));
      return;
    }
    setSubmitting(true);
    try {
      const payload: {
        catalog_key: string;
        name: string;
        allowed_agent_slugs?: string[];
        allowed_remote_tool_names?: string[];
      } = {
        catalog_key: selectedCatalogKey,
        name,
      };
      if (selectedAgentSlugs.length > 0) {
        payload.allowed_agent_slugs = selectedAgentSlugs;
      }
      if (selectedRemoteTools.length > 0) {
        payload.allowed_remote_tool_names = selectedRemoteTools;
      }
      await createMCPExternalConnection(payload);
      toast.success(t("integrations-external-mcp-created"));
      handleCloseCreate();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } };
      toast.error(err?.response?.data?.error || t("an-error-occurred"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevoke = async () => {
    if (!revokeTarget) return;
    try {
      await revokeMCPExternalConnection(revokeTarget.id);
      toast.success(t("integrations-external-mcp-revoked"));
      setRevokeTarget(null);
      await loadData();
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
            <IconCloud size={24} />
            <Title order={4}>{t("integrations-external-mcp-title")}</Title>
          </Group>
          <Text size="sm" c="dimmed">
            {t("integrations-external-mcp-desc")}
          </Text>
        </Stack>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={handleOpenCreate}
          disabled={catalog.length === 0}
        >
          {t("integrations-external-mcp-connect")}
        </Button>
      </Group>

      {loading ? (
        <Text size="sm" c="dimmed">…</Text>
      ) : connections.length === 0 ? (
        <Text size="sm" c="dimmed">{t("integrations-external-mcp-none")}</Text>
      ) : (
        <Stack gap="xs">
          {connections.map((conn) => (
            <Card key={conn.id} withBorder padding="sm" radius="md">
              <Group justify="space-between" align="flex-start">
                <Stack gap={2}>
                  <Group gap="xs">
                    <Text size="sm" fw={600}>{conn.name}</Text>
                    <Badge size="xs" variant="light">{conn.catalog_key}</Badge>
                  </Group>
                  <Text size="xs" c="dimmed">{conn.slug}</Text>
                  {conn.allowed_agent_slugs.length > 0 ? (
                    <Group gap={4}>
                      {conn.allowed_agent_slugs.map((slug) => (
                        <Badge key={slug} size="xs" variant="light">{slug}</Badge>
                      ))}
                    </Group>
                  ) : (
                    <Text size="xs" c="dimmed">{t("integrations-mcp-all-agents")}</Text>
                  )}
                  <Group gap={4}>
                    {(conn.allowed_remote_tool_names.length > 0
                      ? conn.allowed_remote_tool_names
                      : conn.cached_remote_tools.map((tool) => tool.name)
                    ).map((tool) => (
                      <Badge key={tool} size="xs" variant="outline" color="cyan">
                        {localizedExternalTool(conn.catalog_key, tool)}
                      </Badge>
                    ))}
                  </Group>
                </Stack>
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="subtle"
                    color="red"
                    leftSection={<IconTrash size={14} />}
                    onClick={() => setRevokeTarget(conn)}
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
        title={t("integrations-external-mcp-connect")}
        size="lg"
      >
        <Stack gap="sm">
          <TextInput
            label={t("integrations-external-mcp-name")}
            placeholder={t("integrations-external-mcp-name-placeholder")}
            value={connectionName}
            onChange={(e) => setConnectionName(e.currentTarget.value)}
          />
          <MultiSelect
            label={t("integrations-external-mcp-catalog-label")}
            description={selectedCatalog?.description}
            data={catalog.map((c) => ({ value: c.key, label: c.name }))}
            value={selectedCatalogKey ? [selectedCatalogKey] : []}
            onChange={(vals) => setSelectedCatalogKey(vals[0] ?? null)}
            maxValues={1}
            searchable
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
            label={t("integrations-external-mcp-tools-label")}
            description={t("integrations-external-mcp-tools-desc")}
            placeholder={t("integrations-external-mcp-tools-placeholder")}
            data={remoteToolOptions}
            value={selectedRemoteTools}
            onChange={setSelectedRemoteTools}
            searchable
            clearable
            disabled={!selectedCatalog}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={closeCreate}>{t("cancel")}</Button>
            <Button loading={submitting} onClick={() => void handleCreate()}>
              {t("integrations-external-mcp-connect")}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={Boolean(revokeTarget)}
        onClose={() => setRevokeTarget(null)}
        title={t("integrations-external-mcp-revoke-title")}
      >
        <Stack gap="md">
          <Text size="sm">
            {t("integrations-external-mcp-revoke-confirm", {
              name: revokeTarget?.name ?? "",
            })}
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
