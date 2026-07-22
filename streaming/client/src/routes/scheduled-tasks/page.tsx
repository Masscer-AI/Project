import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconCalendarTime,
  IconMenu2,
  IconMessage,
  IconTrash,
} from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import {
  cancelScheduledTask,
  listMyScheduledTasks,
  TScheduledConversationTask,
} from "../../modules/apiCalls";

function truncate(text: string, max = 220): string {
  const trimmed = (text || "").trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

export default function ScheduledTasksPage() {
  const { t } = useTranslation();
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
      setTasks(res.tasks || []);
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
          <Group justify="space-between" align="flex-start" wrap="wrap">
            <Stack gap={4}>
              <Group gap="xs">
                <IconCalendarTime size={28} />
                <Title order={2}>{t("scheduled-tasks-title")}</Title>
              </Group>
              <Text c="dimmed" size="sm">
                {t("scheduled-tasks-page-description")}
              </Text>
            </Stack>
            <Switch
              label={t("scheduled-tasks-include-finished")}
              checked={includeFinished}
              onChange={(e) => setIncludeFinished(e.currentTarget.checked)}
            />
          </Group>

          {loading ? (
            <Group justify="center" py="xl">
              <Loader size="sm" />
            </Group>
          ) : tasks.length === 0 ? (
            <Card withBorder padding="lg" radius="md">
              <Text c="dimmed" size="sm">
                {t("scheduled-tasks-empty")}
              </Text>
            </Card>
          ) : (
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
              {tasks.map((task) => {
                const canCancel =
                  task.status === "pending" || task.status === "running";
                return (
                  <Card
                    key={task.id}
                    withBorder
                    padding="md"
                    radius="md"
                    style={{
                      cursor: task.conversation_id ? "pointer" : "default",
                    }}
                    onClick={() => openConversation(task)}
                  >
                    <Stack gap="sm">
                      <Group justify="space-between" wrap="nowrap" align="flex-start">
                        <Group gap={6}>
                          <Badge size="sm" variant="light" color="violet">
                            {task.status}
                          </Badge>
                          <Badge size="sm" variant="outline" color="gray">
                            {task.schedule_type}
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

                      <Text fw={600} size="sm">
                        {task.schedule_summary || task.next_run_at_local || "—"}
                      </Text>

                      {task.next_run_at_local && (
                        <Text size="xs" c="dimmed">
                          {t("scheduled-task-next-run")}: {task.next_run_at_local}
                          {task.timezone ? ` (${task.timezone})` : ""}
                        </Text>
                      )}

                      <Text size="sm" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>
                        {truncate(task.instruction || "")}
                      </Text>

                      {task.conversation_id && (
                        <Group gap={6} mt={4}>
                          <IconMessage size={14} />
                          <Text size="xs" c="dimmed" lineClamp={1}>
                            {task.conversation_title ||
                              t("scheduled-task-open-conversation")}
                          </Text>
                        </Group>
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
        <Text size="sm" mb="md">
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
      </Modal>
    </main>
  );
}
