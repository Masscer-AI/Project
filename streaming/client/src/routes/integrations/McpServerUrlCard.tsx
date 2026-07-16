import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { Button, Card, Group, Stack, Text, TextInput } from "@mantine/core";
import { IconCopy } from "@tabler/icons-react";
import { listOAuthClients } from "../../modules/apiCalls";

function defaultMcpUrl(): string {
  if (typeof window !== "undefined") {
    return `${window.location.origin}/mcp`;
  }
  return "/mcp";
}

export const McpServerUrlCard = () => {
  const { t } = useTranslation();
  const [mcpUrl, setMcpUrl] = useState(defaultMcpUrl);

  useEffect(() => {
    void listOAuthClients()
      .then((res) => {
        if (res.mcp_url?.startsWith("http")) {
          setMcpUrl(res.mcp_url);
        }
      })
      .catch(() => undefined);
  }, []);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(mcpUrl);
      toast.success(t("copied"));
    } catch {
      toast.error(t("an-error-occurred"));
    }
  }, [mcpUrl, t]);

  return (
    <Card withBorder padding="md" style={{ borderColor: "var(--mantine-color-violet-8)" }}>
      <Stack gap={4}>
        <Text size="sm" fw={600}>{t("oauth-mcp-url-label")}</Text>
        <Text size="xs" c="dimmed">{t("oauth-mcp-url-desc")}</Text>
        <Group align="flex-end" wrap="nowrap" gap="xs">
          <TextInput
            flex={1}
            value={mcpUrl}
            readOnly
            styles={{ input: { fontFamily: "monospace", fontSize: "0.85rem" } }}
          />
          <Button
            variant="light"
            leftSection={<IconCopy size={16} />}
            onClick={() => void handleCopy()}
          >
            {t("copy")}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
};
