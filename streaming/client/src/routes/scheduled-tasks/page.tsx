import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Divider,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconCalendarEvent,
  IconCalendarTime,
  IconClock,
  IconMenu2,
  IconMessage,
  IconPlayerPlay,
  IconRepeat,
  IconRobot,
  IconTrash,
} from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import {
  cancelScheduledTask,
  listMyScheduledTasks,
  TScheduledConversationTask,
} from "../../modules/apiCalls";

function parseInstructionSteps(instruction: string): string[] {
  const trimmed = (instruction || "").trim();
  if (!trimmed) return [];

  const numbered = trimmed
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/^\d+[\).\-:]\s*/, "").trim())
    .filter(Boolean);

  if (numbered.length > 1) return numbered;

  // Fallback: split "1. ... 2. ..." on a single line
  const inline = trimmed
    .split(/(?=\d+[\).\-]\s+)/)
    .map((part) => part.replace(/^\d+[\).\-:]\s*/, "").trim())
    .filter(Boolean);
  return inline.length > 1 ? inline : [trimmed];
}

function formatNextRun(
  localIso: string | null | undefined,
  locale: string
): string | null {
  if (!localIso) return null;
  // Backend sends org-local wall time without offset, e.g. 2026-07-31T13:51:34
  const match = localIso.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/
  );
  if (!match) return localIso;
  const [, year, month, day, hour, minute] = match;
  const d = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute)
  );
  return new Intl.DateTimeFormat(locale, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(d);
}

function statusColor(status: string): string {
  switch ((status || "").toLowerCase()) {
    case "pending":
      return "violet";
    case "running":
      return "blue";
    case "done":
      return "teal";
    case "failed":
      return "red";
    default:
      return "gray";
  }
}

export default function ScheduledTasksPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const [loading, setLoading] = useState(true);
  const [includeFinished, setIncludeFinished] = useState(false);
  const [tasks, setTasks] = useState<TScheduledConversationTask[]>([]);
  const [cancelTarget, setCancelTarget] =
    useState<TScheduledConversationTask | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [confirmOpened, { open: openConfirm, close: closeConfirm }] =
    useDisclosure(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listMyScheduledTasks({
        includeFinished,
        limit: 100,
      });
      // Defensive: cancelled tasks should never appear in the UI.
      setTasks((res.tasks || []).filter((task) => task.status !== "cancelled"));
    } catch (err) {
      console.error(err);
      toast.error(t("scheduled-tasks-load-error"));
    } finally {
      setLoading(false);
    }
  }, [includeFinished, t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const activeCount = useMemo(
    () =>
      tasks.filter(
        (task) => task.status === "pending" || task.status === "running"
      ).length,
    [tasks]
  );

  const requestCancel = (task: TScheduledConversationTask, e: React.MouseEvent) => {
    e.stopPropagation();
    setCancelTarget(task);
    openConfirm();
  };

  const handleConfirmCancel = async () => {
    if (!cancelTarget) return;
    setCancelling(true);
    try {
      await cancelScheduledTask(cancelTarget.id);
      toast.success(t("scheduled-task-cancelled"));
      closeConfirm();
      setCancelTarget(null);
      await refresh();
    } catch (err) {
      console.error(err);
      toast.error(t("scheduled-task-cancel-error"));
    } finally {
      setCancelling(false);
    }
  };

  const openConversation = (task: TScheduledConversationTask) => {
    if (!task.conversation_id) return;
    navigate(`/chat?conversation=${task.conversation_id}`);
  };

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

        <Stack maw="56rem" w="100%" gap="lg" mt={48}>
          <Group justify="space-between" align="flex-start" wrap="wrap" gap="md">
            <Group gap="md" align="flex-start" wrap="nowrap">
              <ThemeIcon
                size={44}
                radius="md"
                variant="light"
                color="violet"
                style={{ flexShrink: 0 }}
              >
                <IconCalendarTime size={24} />
              </ThemeIcon>
              <Stack gap={4}>
                <Title order={2}>{t("scheduled-tasks-title")}</Title>
                <Text size="sm" c="dimmed">
                  {t("scheduled-tasks-page-description")}
                </Text>
              </Stack>
            </Group>
            <Group gap="sm">
              <Badge variant="light" color="violet" leftSection={<IconCalendarEvent size={12} />}>
                {activeCount}
              </Badge>
              <Switch
                label={t("scheduled-tasks-include-finished")}
                checked={includeFinished}
                onChange={(e) => setIncludeFinished(e.currentTarget.checked)}
              />
            </Group>
          </Group>

          {loading ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : tasks.length === 0 ? (
            <Card withBorder padding="xl" radius="md">
              <Stack align="center" gap="sm">
                <Text fw={600}>{t("scheduled-tasks-empty")}</Text>
                <Text size="sm" c="dimmed" ta="center" maw="28rem">
                  {t("scheduled-tasks-empty-hint")}
                </Text>
              </Stack>
            </Card>
          ) : (
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
              {tasks.map((task) => {
                const canCancel =
                  task.status === "pending" || task.status === "running";
                const isRecurring = task.schedule_type === "recurring";
                const title =
                  task.title?.trim() ||
                  t("scheduled-task-untitled");
                const steps = parseInstructionSteps(task.instruction || "");
                const previewSteps = steps.slice(0, 3);
                const extraSteps = Math.max(0, steps.length - previewSteps.length);
                const nextRunLabel = formatNextRun(
                  task.next_run_at_local,
                  i18n.language
                );
                const statusKey = (task.status || "").toLowerCase();
                const accent = statusColor(statusKey);
                const agentSlugs = task.agent_slugs || [];

                return (
                  <Card
                    key={task.id}
                    withBorder
                    padding="md"
                    radius="md"
                    style={{
                      cursor: task.conversation_id ? "pointer" : "default",
                      borderLeft: `3px solid var(--mantine-color-${accent}-6)`,
                    }}
                    onClick={() => openConversation(task)}
                  >
                    <Stack gap="sm" h="100%">
                      <Group justify="space-between" wrap="nowrap" align="flex-start">
                        <Group gap={6}>
                          <Badge size="sm" variant="light" color={accent}>
                            {t(`scheduled-task-status-${statusKey}`, {
                              defaultValue: task.status,
                            })}
                          </Badge>
                          <Badge
                            size="sm"
                            variant="outline"
                            color="gray"
                            leftSection={
                              isRecurring ? (
                                <IconRepeat size={12} />
                              ) : (
                                <IconPlayerPlay size={12} />
                              )
                            }
                          >
                            {isRecurring
                              ? t("scheduled-task-type-recurring")
                              : t("scheduled-task-type-once")}
                          </Badge>
                        </Group>
                        {canCancel && (
                          <Tooltip label={t("scheduled-task-cancel")}>
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              size="sm"
                              aria-label={t("scheduled-task-cancel")}
                              onClick={(e) => requestCancel(task, e)}
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          </Tooltip>
                        )}
                      </Group>

                      <Text fw={600} size="md" lineClamp={2} style={{ lineHeight: 1.35 }}>
                        {title}
                      </Text>

                      <Group gap={8} wrap="nowrap" align="flex-start">
                        <ThemeIcon
                          size={28}
                          radius="sm"
                          variant="light"
                          color="violet"
                          style={{ flexShrink: 0 }}
                        >
                          <IconClock size={16} />
                        </ThemeIcon>
                        <Stack gap={2} style={{ minWidth: 0 }}>
                          <Text size="sm" fw={500} lineClamp={2}>
                            {nextRunLabel || task.schedule_summary || "—"}
                            {task.timezone ? (
                              <Text span size="xs" c="dimmed" ml={6}>
                                {task.timezone}
                              </Text>
                            ) : null}
                          </Text>
                          {isRecurring && task.schedule_summary && (
                            <Text size="xs" c="dimmed" lineClamp={2}>
                              {task.schedule_summary}
                            </Text>
                          )}
                        </Stack>
                      </Group>

                      {agentSlugs.length > 0 && (
                        <Stack gap={6}>
                          <Group gap={6}>
                            <IconRobot size={14} style={{ opacity: 0.7 }} />
                            <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
                              {t("scheduled-task-agents")}
                            </Text>
                          </Group>
                          <Group gap={6}>
                            {agentSlugs.map((slug) => (
                              <Badge key={slug} size="xs" variant="light" color="gray">
                                {slug}
                              </Badge>
                            ))}
                          </Group>
                        </Stack>
                      )}

                      {previewSteps.length > 0 && (
                        <Stack gap={4}>
                          <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
                            {t("scheduled-task-steps", { count: steps.length })}
                          </Text>
                          <Stack gap={4}>
                            {previewSteps.map((step, idx) => (
                              <Group key={idx} gap={8} align="flex-start" wrap="nowrap">
                                <Text
                                  size="xs"
                                  c="violet.4"
                                  fw={700}
                                  style={{ width: 14, flexShrink: 0 }}
                                >
                                  {idx + 1}
                                </Text>
                                <Text size="sm" c="dimmed" lineClamp={2}>
                                  {step}
                                </Text>
                              </Group>
                            ))}
                            {extraSteps > 0 && (
                              <Text size="xs" c="dimmed" pl={22}>
                                {t("scheduled-task-steps-more", { count: extraSteps })}
                              </Text>
                            )}
                          </Stack>
                        </Stack>
                      )}

                      {task.conversation_id && (
                        <>
                          <Divider mt="auto" />
                          <Group gap={6} justify="space-between" wrap="nowrap">
                            <Group gap={6} style={{ minWidth: 0 }}>
                              <IconMessage size={14} style={{ opacity: 0.7, flexShrink: 0 }} />
                              <Text size="xs" c="dimmed" lineClamp={1}>
                                {task.conversation_title ||
                                  t("scheduled-task-open-conversation")}
                              </Text>
                            </Group>
                            <Text size="xs" c="violet.4" style={{ flexShrink: 0 }}>
                              {t("scheduled-task-open")}
                            </Text>
                          </Group>
                        </>
                      )}
                    </Stack>
                  </Card>
                );
              })}
            </SimpleGrid>
          )}
        </Stack>
      </div>

      <Modal
        opened={confirmOpened}
        onClose={() => {
          if (!cancelling) {
            closeConfirm();
            setCancelTarget(null);
          }
        }}
        title={t("scheduled-task-cancel-confirm-title")}
        size="sm"
        centered
      >
        <Stack gap="md">
          {cancelTarget?.title?.trim() && (
            <Text size="sm" fw={600}>
              {cancelTarget.title.trim()}
            </Text>
          )}
          <Text size="sm" c="dimmed">
            {t("scheduled-task-cancel-confirm")}
          </Text>
          <Group justify="flex-end" gap="xs">
            <Button
              variant="default"
              onClick={() => {
                closeConfirm();
                setCancelTarget(null);
              }}
              disabled={cancelling}
            >
              {t("cancel")}
            </Button>
            <Button color="red" onClick={handleConfirmCancel} loading={cancelling}>
              {t("scheduled-task-cancel")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </main>
  );
}
