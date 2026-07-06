import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Checkbox,
  Collapse,
  Group,
  Progress,
  Stack,
  Text,
  Title,
  useMantineColorScheme,
} from "@mantine/core";
import { IconChevronDown, IconChevronUp, IconListCheck } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import {
  getAssignments,
  updateAssignmentStep,
} from "../../modules/apiCalls";
import { useStore } from "../../modules/store";
import type { TAssignmentStep, TUserAssignment } from "../../types/assignments";
import { focusOnboardingTarget } from "./onboardingFocus";
import "./AssignmentsPanel.css";

type AssignmentsPanelProps = {
  disabled?: boolean;
  /** Fixed dock visible on every authenticated page */
  floating?: boolean;
};

const AUTH_PATHS = new Set([
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
]);

export const AssignmentsPanel: React.FC<AssignmentsPanelProps> = ({
  disabled = false,
  floating = false,
}) => {
  const { t } = useTranslation();
  const { colorScheme } = useMantineColorScheme();
  const location = useLocation();
  const navigate = useNavigate();
  const agentTaskStatus = useStore((s) => s.agentTaskStatus);
  const user = useStore((s) => s.user);
  const prevTaskStatusRef = useRef<string | null>(null);

  const [assignments, setAssignments] = useState<TUserAssignment[]>([]);
  const [opened, setOpened] = useState(true);
  const [loading, setLoading] = useState(false);
  const prevCountRef = useRef(0);

  const hasToken =
    typeof window !== "undefined" && Boolean(localStorage.getItem("token"));
  const isAuthPage = AUTH_PATHS.has(location.pathname);

  const activeAssignments = assignments.filter(
    (a) => a.status !== "done" && a.status !== "archived"
  );

  const pendingStepCount = activeAssignments.reduce((acc, a) => {
    return (
      acc +
      (a.metadata?.steps?.filter((s) => s.status !== "done").length ?? 0)
    );
  }, 0);

  const fetchAssignments = useCallback(async () => {
    if (disabled || !hasToken || isAuthPage) return;
    setLoading(true);
    try {
      const res = await getAssignments();
      const list = res.assignments ?? [];
      if (
        prevCountRef.current > 0 &&
        list.length > prevCountRef.current
      ) {
        toast.success(t("assignments-new-task-assigned"));
      }
      prevCountRef.current = list.length;
      setAssignments(list);
    } catch (e) {
      console.error("Failed to load assignments", e);
    } finally {
      setLoading(false);
    }
  }, [disabled, hasToken, isAuthPage, t]);

  useEffect(() => {
    void fetchAssignments();
  }, [fetchAssignments, location.pathname, user?.id]);

  useEffect(() => {
    const prev = prevTaskStatusRef.current;
    prevTaskStatusRef.current = agentTaskStatus;
    if (prev && !agentTaskStatus) {
      void fetchAssignments();
    }
  }, [agentTaskStatus, fetchAssignments]);

  const handleStepAction = async (step: TAssignmentStep) => {
    const button = step.button;
    const actionType = button?.action_type ?? "navigate";
    const target = button?.action_target ?? step.app_url ?? null;

    if (actionType === "focus_element") {
      const focusKey = target;
      if (!focusKey) return;
      if (step.route && step.route !== location.pathname + location.search) {
        navigate(step.route);
      }
      const ok = await focusOnboardingTarget(focusKey);
      if (!ok) {
        toast.error(t("assignments-target-not-found"));
      }
      return;
    }

    // navigate (default)
    const path = step.route || (target && target.startsWith("/") ? target : null);
    if (!path) return;
    navigate(path);
  };

  const handleToggleStep = async (
    assignment: TUserAssignment,
    stepId: string,
    checked: boolean
  ) => {
    const newStatus = checked ? "done" : "pending";
    try {
      const updated = await updateAssignmentStep(
        assignment.id,
        stepId,
        newStatus
      );
      setAssignments((prev) =>
        prev.map((a) => (a.id === updated.id ? updated : a))
      );
    } catch (e) {
      console.error(e);
      toast.error(t("an-error-occurred"));
    }
  };

  if (disabled || isAuthPage || !hasToken || activeAssignments.length === 0) {
    return null;
  }

  const cardStyle: React.CSSProperties | undefined = floating
    ? {
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 250,
        width: "min(360px, calc(100vw - 32px))",
        maxHeight: opened ? "min(70vh, 520px)" : undefined,
        display: "flex",
        flexDirection: "column",
        boxShadow:
          colorScheme === "dark"
            ? "0 8px 32px rgba(0, 0, 0, 0.45)"
            : "var(--mantine-shadow-md)",
      }
    : undefined;

  return (
    <Card
      withBorder
      padding="sm"
      radius="md"
      mb={floating ? 0 : "sm"}
      style={cardStyle}
    >
      <Group justify="space-between" wrap="nowrap" mb={opened ? "xs" : 0}>
        <Group gap="xs" wrap="nowrap">
          <IconListCheck size={18} />
          <Title order={6}>{t("assignments-panel-title")}</Title>
          {pendingStepCount > 0 && (
            <Badge size="sm" color="violet" variant="light">
              {pendingStepCount}
            </Badge>
          )}
        </Group>
        <ActionIcon
          variant="subtle"
          color="gray"
          size="sm"
          onClick={() => setOpened((o) => !o)}
          aria-label={opened ? "Collapse" : t("expand")}
        >
          {opened ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
        </ActionIcon>
      </Group>

      <Collapse in={opened}>
        <Stack
          gap="md"
          mt="xs"
          style={
            floating
              ? { overflowY: "auto", maxHeight: "calc(min(70vh, 520px) - 48px)" }
              : undefined
          }
        >
          {activeAssignments.map((assignment) => (
            <Stack key={assignment.id} gap={6}>
              <Group justify="space-between" wrap="nowrap">
                <Text size="sm" fw={600} truncate>
                  {assignment.title}
                </Text>
                <Text size="xs" c="dimmed">
                  {Math.round((assignment.progress ?? 0) * 100)}%
                </Text>
              </Group>
              <Progress
                value={(assignment.progress ?? 0) * 100}
                size="sm"
                color="violet"
              />
              <Stack gap={4}>
                {assignment.metadata.steps.map((step) => (
                  <Group key={step.id} gap="xs" wrap="nowrap" align="flex-start">
                    <Checkbox
                      checked={step.status === "done"}
                      onChange={(e) => {
                        const checked = e.currentTarget.checked;
                        void handleToggleStep(assignment, step.id, checked);
                      }}
                      color="violet"
                      size="sm"
                      mt={2}
                      disabled={loading}
                    />
                    <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
                      <Text
                        size="sm"
                        td={step.status === "done" ? "line-through" : undefined}
                        c={step.status === "done" ? "dimmed" : undefined}
                      >
                        {step.title}
                      </Text>
                      {step.description && step.status !== "done" && (
                        <Text size="xs" c="dimmed" lineClamp={2}>
                          {step.description}
                        </Text>
                      )}
                      {step.status !== "done" &&
                        (() => {
                          const hasAction =
                            (step.button &&
                              step.button.action_type !== "none" &&
                              step.button.action_target) ||
                            step.app_url;
                          if (!hasAction) return null;
                          const label =
                            step.button?.text || t("assignments-open-step");
                          return (
                            <Button
                              variant="light"
                              color="violet"
                              size="compact-xs"
                              mt={2}
                              style={{ alignSelf: "flex-start" }}
                              onClick={() => void handleStepAction(step)}
                            >
                              {label}
                            </Button>
                          );
                        })()}
                    </Stack>
                  </Group>
                ))}
              </Stack>
            </Stack>
          ))}
        </Stack>
      </Collapse>
    </Card>
  );
};
