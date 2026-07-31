import React, { useEffect, useState } from "react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import "./page.css";
import { getWhatsappNumbers } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Stack,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconBrandWhatsapp,
  IconChevronRight,
  IconMenu2,
  IconMessages,
  IconRobot,
  IconSettings,
  IconSparkles,
  IconUsers,
} from "@tabler/icons-react";
import {
  countEnabledCapabilities,
  formatWhatsappPhone,
  type WhatsappLine,
} from "./shared";

function StatChip({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <Tooltip label={label} withArrow>
      <Group
        gap={6}
        wrap="nowrap"
        px="sm"
        py={6}
        style={{
          borderRadius: "var(--mantine-radius-sm)",
          background: "var(--mantine-color-dark-6)",
          border: "1px solid var(--mantine-color-dark-4)",
        }}
      >
        <ThemeIcon size={22} radius="sm" variant="light" color="gray">
          {icon}
        </ThemeIcon>
        <Stack gap={0}>
          <Text size="xs" c="dimmed" lh={1.2}>
            {label}
          </Text>
          <Text size="sm" fw={600} lh={1.2}>
            {value}
          </Text>
        </Stack>
      </Group>
    </Tooltip>
  );
}

function WhatsappLineCard({ line }: { line: WhatsappLine }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const phone = formatWhatsappPhone(line.number);
  const toolsEnabled = countEnabledCapabilities(line.capabilities);
  const displayName = (line.name || "").trim() || phone;

  return (
    <Card
      withBorder
      padding="md"
      radius="md"
      style={{ cursor: "pointer" }}
      onClick={() => navigate(`/whatsapp/${line.id}`)}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
        <Group gap="md" wrap="nowrap" style={{ minWidth: 0, flex: 1 }}>
          <ThemeIcon
            size={48}
            radius="md"
            variant="light"
            color="teal"
            style={{ flexShrink: 0 }}
          >
            <IconBrandWhatsapp size={28} />
          </ThemeIcon>

          <Stack gap={4} style={{ minWidth: 0, flex: 1 }}>
            <Group gap="xs" wrap="wrap">
              <Text fw={700} size="lg" lineClamp={1}>
                {displayName}
              </Text>
              {line.verified ? (
                <Badge size="sm" variant="light" color="teal">
                  {t("whatsapp-verified")}
                </Badge>
              ) : (
                <Badge size="sm" variant="light" color="gray">
                  {t("whatsapp-unverified")}
                </Badge>
              )}
            </Group>

            <Text size="sm" c="dimmed" ff="monospace">
              {phone}
            </Text>

            <Group gap="xs" mt={6} wrap="wrap">
              <StatChip
                icon={<IconRobot size={14} />}
                label={t("agent")}
                value={line.agent?.name || "—"}
              />
              <StatChip
                icon={<IconMessages size={14} />}
                label={t("whatsapp-conversations")}
                value={line.conversations_count ?? 0}
              />
              <StatChip
                icon={<IconSparkles size={14} />}
                label={t("whatsapp-tools-enabled")}
                value={toolsEnabled}
              />
            </Group>
          </Stack>
        </Group>

        <IconChevronRight
          size={20}
          style={{ flexShrink: 0, opacity: 0.45, marginTop: 4 }}
        />
      </Group>

      <Group
        justify="flex-end"
        gap="xs"
        mt="md"
        onClick={(e) => e.stopPropagation()}
      >
        <Button
          size="xs"
          variant="default"
          leftSection={<IconUsers size={14} />}
          onClick={() => navigate(`/whatsapp/${line.id}?tab=contacts`)}
        >
          {t("whatsapp-contacts")}
        </Button>
        <Button
          size="xs"
          variant="default"
          leftSection={<IconSettings size={14} />}
          onClick={() => navigate(`/whatsapp/${line.id}?tab=settings`)}
        >
          {t("whatsapp-tab-settings")}
        </Button>
        <Button
          size="xs"
          variant="light"
          color="teal"
          leftSection={<IconMessages size={14} />}
          onClick={() =>
            navigate(`/dashboard?wsNumberId=${line.id}&channel=whatsapp`)
          }
        >
          {t("view-conversations")}
        </Button>
      </Group>
    </Card>
  );
}

export default function Whatsapp() {
  const { t } = useTranslation();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const [numbers, setNumbers] = useState<WhatsappLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getWhatsappNumbers()
      .then((res) => {
        if (!cancelled) {
          setNumbers(res as WhatsappLine[]);
          setLoadError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(t("whatsapp-load-error"));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          padding: 24,
          overflowY: "auto",
          minHeight: "100vh",
          display: "flex",
          justifyContent: "center",
        }}
        className="relative"
      >
        {!chatState.isSidebarOpened && (
          <Box pos="absolute" top={24} left={24} style={{ zIndex: 10 }}>
            <ActionIcon variant="subtle" color="gray" onClick={toggleSidebar}>
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box px="md" w="100%" maw="48rem" mx="auto">
          <Group gap="sm" justify="center" mb="sm" mt="md">
            <ThemeIcon size={40} radius="md" variant="light" color="teal">
              <IconBrandWhatsapp size={24} />
            </ThemeIcon>
            <Title order={2}>{t("whatsapp")}</Title>
          </Group>
          <Text ta="center" mb="xs">
            {t("whatsapp-intro")}
          </Text>
          <Text ta="center" size="sm" c="dimmed" mb="xl">
            {t("whatsapp-provision-note")}
          </Text>

          <Group justify="space-between" align="baseline" mb="sm">
            <Title order={4}>{t("whatsapp-your-numbers")}</Title>
            {!loading && !loadError ? (
              <Text size="sm" c="dimmed">
                {t("whatsapp-lines-count", { count: numbers.length })}
              </Text>
            ) : null}
          </Group>

          {loading ? (
            <Stack align="center" py="xl">
              <Loader color="teal" />
            </Stack>
          ) : loadError ? (
            <Text c="red">{loadError}</Text>
          ) : numbers.length === 0 ? (
            <Card withBorder padding="xl" radius="md">
              <Stack align="center" gap="sm">
                <ThemeIcon size={48} radius="md" variant="light" color="gray">
                  <IconBrandWhatsapp size={28} />
                </ThemeIcon>
                <Text c="dimmed" ta="center">
                  {t("whatsapp-empty-lines")}
                </Text>
              </Stack>
            </Card>
          ) : (
            <Stack gap="md">
              {numbers.map((line) => (
                <WhatsappLineCard key={line.id} line={line} />
              ))}
            </Stack>
          )}
        </Box>
      </div>
    </main>
  );
}
