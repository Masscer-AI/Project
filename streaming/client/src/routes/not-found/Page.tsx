import { Box, Button, Container, Paper, Stack, Text, ThemeIcon, Title } from "@mantine/core";
import { IconHome, IconMoodSad } from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";
import i18n from "../../i18next";

export const NotFoundPage = () => {
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
            <ThemeIcon color="violet" variant="light" size={56} radius="xl">
              <IconMoodSad size={30} />
            </ThemeIcon>
            <Stack align="center" gap="xs">
              <Title order={1} ta="center">
                {i18n.t("page-not-found")}
              </Title>
              <Text c="dimmed" ta="center">
                {i18n.t("page-not-found-description")}
              </Text>
            </Stack>
            <Button
              leftSection={<IconHome size={16} />}
              onClick={() => navigate("/")}
            >
              {i18n.t("go-to-home")}
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
};
