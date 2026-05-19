import React from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Anchor,
  Badge,
  Box,
  Group,
  Stack,
  Text,
  Title,
} from "@mantine/core";

type SharedChatHeaderProps = {
  title: string;
};

export const SharedChatHeader = ({ title }: SharedChatHeaderProps) => {
  const { t } = useTranslation();

  return (
    <Box
      className="rounded-none md:rounded-xl w-full shadow-lg z-10 min-w-0 p-3 md:p-4"
      style={{
        background: "var(--bg-contrast-color)",
        border: "1px solid var(--hovered-color)",
      }}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
        <Stack gap={4} className="min-w-0 flex-1">
          <Group gap="xs" wrap="wrap">
            <Badge variant="light" color="gray" size="sm">
              {t("shared-conversation-view-badge")}
            </Badge>
            <Text size="sm" c="dimmed">
              {t("shared-conversation-read-only")}
            </Text>
          </Group>
          <Title order={3} className="break-words">
            {title}
          </Title>
        </Stack>
        <Anchor component={Link} to="/" size="sm" c="violet" className="shrink-0">
          {t("shared-conversation-open-app")}
        </Anchor>
      </Group>
    </Box>
  );
};
