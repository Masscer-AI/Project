import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Accordion,
  Badge,
  Button,
  Card,
  Divider,
  Group,
  Modal,
  Stack,
  TagsInput,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconCopy,
  IconKey,
  IconPlus,
  IconSettings,
  IconTrash,
} from "@tabler/icons-react";
import {
  createOAuthClient,
  listOAuthClients,
  revokeOAuthClient,
  TOAuthClientCreated,
  TOAuthClientSummary,
} from "../../modules/apiCalls";
import { McpCredentialsSection } from "./McpCredentialsSection";

const CLAUDE_REDIRECT = "https://claude.ai/api/mcp/auth_callback";
const CHATGPT_REDIRECT_PREFIX = "https://chatgpt.com/connector/oauth/";

function defaultMcpUrl(): string {
  if (typeof window !== "undefined") {
    return `${window.location.origin}/mcp`;
  }
  return "/mcp";
}

function McpUrlField({
  label,
  description,
  value,
  onCopy,
  copyLabel,
}: {
  label: string;
  description?: string;
  value: string;
  onCopy: () => void;
  copyLabel: string;
}) {
  return (
    <Stack gap={4}>
      <Text size="sm" fw={600}>{label}</Text>
      {description ? <Text size="xs" c="dimmed">{description}</Text> : null}
      <Group align="flex-end" wrap="nowrap" gap="xs">
        <TextInput
          flex={1}
          value={value}
          readOnly
          styles={{ input: { fontFamily: "monospace", fontSize: "0.85rem" } }}
        />
        <Button
          variant="light"
          leftSection={<IconCopy size={16} />}
          onClick={onCopy}
        >
          {copyLabel}
        </Button>
      </Group>
    </Stack>
  );
}

type OAuthClientsSectionProps = {
  onManualCredentialCreated?: () => void;
};

export const OAuthClientsSection = ({
  onManualCredentialCreated,
}: OAuthClientsSectionProps) => {
  const { t } = useTranslation();
  const [clients, setClients] = useState<TOAuthClientSummary[]>([]);
  const [mcpUrl, setMcpUrl] = useState(defaultMcpUrl);
  const [loading, setLoading] = useState(true);
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [created, setCreated] = useState<TOAuthClientCreated | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<TOAuthClientSummary | null>(null);
  const [clientName, setClientName] = useState("");
  const [redirectUris, setRedirectUris] = useState<string[]>([CLAUDE_REDIRECT]);
  const [submitting, setSubmitting] = useState(false);

  const loadClients = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listOAuthClients();
      setClients(res.clients || []);
      if (res.mcp_url?.startsWith("http")) {
        setMcpUrl(res.mcp_url);
      }
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadClients();
  }, [loadClients]);

  const resetForm = () => {
    setClientName("");
    setRedirectUris([CLAUDE_REDIRECT]);
    setCreated(null);
  };

  const handleCreate = async () => {
    const name = clientName.trim();
    if (!name) {
      toast.error(t("oauth-client-name-required"));
      return;
    }
    if (redirectUris.length === 0) {
      toast.error(t("oauth-client-redirect-required"));
      return;
    }
    setSubmitting(true);
    try {
      const res = await createOAuthClient({
        client_name: name,
        redirect_uris: redirectUris,
        confidential: true,
      });
      setCreated(res);
      if (res.mcp_url?.startsWith("http")) {
        setMcpUrl(res.mcp_url);
      }
      await loadClients();
      toast.success(t("oauth-client-created"));
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
      await revokeOAuthClient(revokeTarget.id);
      toast.success(t("oauth-client-revoked"));
      setRevokeTarget(null);
      await loadClients();
    } catch {
      toast.error(t("an-error-occurred"));
    }
  };

  const handleCopyMcpUrl = async () => {
    try {
      await navigator.clipboard.writeText(mcpUrl);
      toast.success(t("copied"));
    } catch {
      toast.error(t("an-error-occurred"));
    }
  };

  return (
    <Stack gap="md">
      <Accordion variant="separated" radius="md">
        <Accordion.Item value="oauth-advanced">
          <Accordion.Control icon={<IconSettings size={18} />}>
            <Stack gap={2}>
              <Text size="sm" fw={600}>{t("oauth-advanced-settings")}</Text>
              <Text size="xs" c="dimmed">
                {t("oauth-advanced-settings-desc")}
              </Text>
            </Stack>
          </Accordion.Control>
          <Accordion.Panel>
            <Stack gap="lg">
              <McpCredentialsSection
                variant="create-advanced"
                onCreated={onManualCredentialCreated}
              />

              <Divider />

              <Group justify="space-between" align="flex-start">
                <Stack gap={4}>
                  <Group gap="sm">
                    <IconKey size={20} />
                    <Title order={5}>{t("oauth-clients-title")}</Title>
                  </Group>
                  <Text size="sm" c="dimmed">
                    {t("oauth-clients-desc")}
                  </Text>
                </Stack>
                <Button
                  size="sm"
                  leftSection={<IconPlus size={16} />}
                  onClick={() => {
                    resetForm();
                    openCreate();
                  }}
                >
                  {t("oauth-clients-create")}
                </Button>
              </Group>

              {loading ? (
                <Text size="sm" c="dimmed">…</Text>
              ) : clients.length === 0 ? (
                <Text size="sm" c="dimmed">{t("oauth-clients-none")}</Text>
              ) : (
                <Stack gap="xs">
                  {clients.map((client) => (
                    <Card key={client.id} withBorder padding="sm">
                      <Group justify="space-between" align="flex-start">
                        <Stack gap={2}>
                          <Text fw={600} size="sm">{client.client_name}</Text>
                          <Text size="xs" c="dimmed" style={{ wordBreak: "break-all" }}>
                            {client.client_id}
                          </Text>
                          {client.redirect_uris.map((uri) => (
                            <Badge key={uri} size="xs" variant="light">{uri}</Badge>
                          ))}
                        </Stack>
                        <Button
                          size="xs"
                          variant="subtle"
                          color="red"
                          leftSection={<IconTrash size={14} />}
                          onClick={() => setRevokeTarget(client)}
                        >
                          {t("oauth-clients-revoke")}
                        </Button>
                      </Group>
                    </Card>
                  ))}
                </Stack>
              )}
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      <Modal opened={createOpened} onClose={() => { closeCreate(); resetForm(); }} title={t("oauth-clients-create")} size="lg">
        {created ? (
          <Stack gap="sm">
            <Text size="sm">{t("oauth-client-created-hint")}</Text>
            <McpUrlField
              label={t("oauth-mcp-url-label")}
              description={t("oauth-mcp-url-claude-hint")}
              value={created.mcp_url || mcpUrl}
              onCopy={() => void handleCopyMcpUrl()}
              copyLabel={t("copy")}
            />
            <TextInput label="Client ID" value={created.client_id} readOnly />
            {created.client_secret && (
              <TextInput label="Client Secret" value={created.client_secret} readOnly />
            )}
            <Text size="xs" c="dimmed">{t("oauth-client-secret-once")}</Text>
            <Group justify="flex-end">
              <Button onClick={() => { closeCreate(); resetForm(); }}>{t("close")}</Button>
            </Group>
          </Stack>
        ) : (
          <Stack gap="sm">
            <McpUrlField
              label={t("oauth-mcp-url-label")}
              description={t("oauth-mcp-url-claude-hint")}
              value={mcpUrl}
              onCopy={() => void handleCopyMcpUrl()}
              copyLabel={t("copy")}
            />
            <TextInput
              label={t("oauth-client-name-label")}
              value={clientName}
              onChange={(e) => setClientName(e.currentTarget.value)}
              placeholder="Claude Hosted Connector"
            />
            <TagsInput
              label={t("oauth-client-redirect-label")}
              description={t("oauth-client-redirect-desc")}
              value={redirectUris}
              onChange={setRedirectUris}
              placeholder={CHATGPT_REDIRECT_PREFIX}
            />
            <Group gap="xs">
              <Button size="xs" variant="light" onClick={() => setRedirectUris([CLAUDE_REDIRECT])}>
                Claude
              </Button>
            </Group>
            <Group justify="flex-end">
              <Button variant="default" onClick={closeCreate}>{t("cancel")}</Button>
              <Button loading={submitting} onClick={() => void handleCreate()}>
                {t("oauth-clients-create")}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      <Modal opened={Boolean(revokeTarget)} onClose={() => setRevokeTarget(null)} title={t("oauth-clients-revoke-title")}>
        <Stack gap="md">
          <Text size="sm">
            {t("oauth-clients-revoke-confirm", { name: revokeTarget?.client_name ?? "" })}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRevokeTarget(null)}>{t("cancel")}</Button>
            <Button color="red" onClick={() => void handleRevoke()}>{t("oauth-clients-revoke")}</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
};
