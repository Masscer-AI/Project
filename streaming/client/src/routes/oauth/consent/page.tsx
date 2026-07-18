import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Button,
  Card,
  Group,
  MultiSelect,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  approveOAuthAuthorizeRequest,
  denyOAuthAuthorizeRequest,
  getOAuthAuthorizeRequest,
  TOAuthAuthorizeRequest,
} from "../../../modules/apiCalls";
import { loginUrlWithNext } from "../../../utils/loginRedirect";
import { useLocalizedToolName } from "../../../utils/localizedToolName";
import { mcpToolGroupLabel } from "../../../utils/mcpToolGroupLabel";

export default function OAuthConsentPage() {
  const { t } = useTranslation();
  const localizedToolName = useLocalizedToolName();
  const [searchParams] = useSearchParams();
  const requestId = searchParams.get("req") || "";

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [detail, setDetail] = useState<TOAuthAuthorizeRequest | null>(null);
  const [credentialName, setCredentialName] = useState("");
  const [selectedAgentSlugs, setSelectedAgentSlugs] = useState<string[]>([]);
  const [selectedToolNames, setSelectedToolNames] = useState<string[]>([]);

  const loginRedirect = useMemo(() => {
    const path = `/oauth/consent?req=${encodeURIComponent(requestId)}`;
    return loginUrlWithNext(path);
  }, [requestId]);

  // Mantine MultiSelect grouped format: { group, items: [{ value, label }] }
  const toolOptions = useMemo(() => {
    if (!detail?.tool_presets?.length) return [];
    return detail.tool_presets.map((preset) => ({
      group: mcpToolGroupLabel(preset.group, t),
      items: (preset.items ?? []).map((tool) => ({
        value: tool,
        label: localizedToolName(tool),
      })),
    }));
  }, [detail, localizedToolName, t]);

  const agentOptions = useMemo(
    () =>
      (detail?.agents ?? []).map((a) => ({ value: a.slug, label: a.name })),
    [detail]
  );

  const allAgentSlugs = useMemo(
    () => agentOptions.map((a) => a.value),
    [agentOptions]
  );

  const allToolValues = useMemo(
    () =>
      (detail?.tool_presets ?? []).flatMap((preset) => preset.items ?? []),
    [detail]
  );

  const loadDetail = useCallback(async () => {
    if (!requestId) {
      setLoading(false);
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = loginRedirect;
      return;
    }
    setLoading(true);
    try {
      const data = await getOAuthAuthorizeRequest(requestId);
      setDetail({
        ...data,
        agents: data.agents ?? [],
        tool_presets: (data.tool_presets ?? []).map((preset) => ({
          group: preset.group,
          items: preset.items ?? [],
        })),
      });
      setCredentialName(data.client_name);
    } catch (error: unknown) {
      const err = error as { response?: { status?: number } };
      if (err?.response?.status === 401) {
        window.location.href = loginRedirect;
        return;
      }
      toast.error(t("oauth-consent-load-error"));
    } finally {
      setLoading(false);
    }
  }, [requestId, loginRedirect, t]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const handleApprove = async () => {
    if (!requestId) return;
    setSubmitting(true);
    try {
      const payload: {
        credential_name?: string;
        allowed_agent_slugs?: string[];
        allowed_tool_names?: string[];
      } = { credential_name: credentialName.trim() || detail?.client_name };
      if (selectedAgentSlugs.length > 0) {
        payload.allowed_agent_slugs = selectedAgentSlugs;
      }
      if (selectedToolNames.length > 0) {
        payload.allowed_tool_names = selectedToolNames;
      }
      const res = await approveOAuthAuthorizeRequest(requestId, payload);
      window.location.href = res.redirect_url;
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } };
      toast.error(err?.response?.data?.error || t("an-error-occurred"));
      setSubmitting(false);
    }
  };

  const handleDeny = async () => {
    if (!requestId) return;
    setSubmitting(true);
    try {
      const res = await denyOAuthAuthorizeRequest(requestId);
      window.location.href = res.redirect_url;
    } catch {
      toast.error(t("an-error-occurred"));
      setSubmitting(false);
    }
  };

  if (!requestId) {
    return (
      <Stack maw={480} mx="auto" mt={80}>
        <Text>{t("oauth-consent-missing-request")}</Text>
      </Stack>
    );
  }

  if (loading) {
    return (
      <Stack maw={480} mx="auto" mt={80}>
        <Text c="dimmed">…</Text>
      </Stack>
    );
  }

  if (!detail) {
    return (
      <Stack maw={480} mx="auto" mt={80}>
        <Text>{t("oauth-consent-load-error")}</Text>
      </Stack>
    );
  }

  return (
    <Stack maw={520} mx="auto" mt={80} gap="md">
      <Title order={2}>{t("oauth-consent-title")}</Title>
      <Text size="sm" c="dimmed">
        {t("oauth-consent-description", { client: detail.client_name })}
      </Text>

      <Card withBorder padding="md">
        <Stack gap="sm">
          <TextInput
            label={t("oauth-consent-credential-name")}
            value={credentialName}
            onChange={(e) => setCredentialName(e.currentTarget.value)}
          />
          <Stack gap={4}>
            <MultiSelect
              label={t("integrations-mcp-agents-label")}
              description={t("integrations-mcp-agents-desc")}
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
                onClick={() => setSelectedToolNames(allToolValues)}
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
          <Group justify="flex-end" mt="sm">
            <Button variant="default" onClick={() => void handleDeny()} disabled={submitting}>
              {t("oauth-consent-deny")}
            </Button>
            <Button onClick={() => void handleApprove()} loading={submitting}>
              {t("oauth-consent-approve")}
            </Button>
          </Group>
        </Stack>
      </Card>
    </Stack>
  );
}
