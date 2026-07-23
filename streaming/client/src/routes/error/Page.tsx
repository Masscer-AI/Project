import { Box, Button, Container, Paper, Stack, Text, ThemeIcon, Title } from "@mantine/core";
import { IconAlertTriangle, IconMessageCircle, IconRefresh } from "@tabler/icons-react";
import React from "react";
import { useNavigate } from "react-router-dom";
import i18n from "../../i18next";

export const ErrorPage = () => {
  const navigate = useNavigate();

  return (
    <Box
      mih="100vh"
      p="md"
      style={{ display: "grid", placeItems: "center" }}
    >
      <Container size={460} w="100%">
        <Paper withBorder shadow="sm" p="xl" radius="md">
          <Stack align="center" gap="md">
            <ThemeIcon color="red" variant="light" size={56} radius="xl">
              <IconAlertTriangle size={30} />
            </ThemeIcon>
            <Stack align="center" gap="xs">
              <Title order={1} ta="center">
                {i18n.t("unexpected-error-title")}
              </Title>
              <Text c="dimmed" ta="center">
                {i18n.t("unexpected-error-description")}
              </Text>
            </Stack>
            <Stack w="100%" gap="xs">
              <Button
                leftSection={<IconRefresh size={16} />}
                onClick={() => window.location.reload()}
              >
                {i18n.t("try-again")}
              </Button>
              <Button
                variant="default"
                leftSection={<IconMessageCircle size={16} />}
                onClick={() => navigate("/chat")}
              >
                {i18n.t("go-to-chats")}
              </Button>
            </Stack>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
};
