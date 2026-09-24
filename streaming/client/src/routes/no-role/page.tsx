import React from "react";
import { useTranslation } from "react-i18next";
import { Box, Stack, Text } from "@mantine/core";
import { AppPage } from "../../components/AppPage/AppPage";

export default function NoRolePage() {
  const { t } = useTranslation();

  return (
    <AppPage title={t("no-role-page-title")}>
      <Box px="md" w="100%" maw="32rem" mx="auto">
        <Stack align="center" gap="sm" mt="xl" pt="xl">
          <Text ta="center" c="dimmed" size="sm">
            {t("no-role-page-description")}
          </Text>
        </Stack>
      </Box>
    </AppPage>
  );
}
