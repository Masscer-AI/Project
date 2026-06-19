import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Card,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
} from "@mantine/core";
import {
  IconBrain,
  IconDatabase,
  IconFileText,
} from "@tabler/icons-react";
import {
  getAgents,
  getConversationStats,
  getConversations,
  getDocumentTemplates,
  getDocuments,
  getUserCompletions,
} from "../../modules/apiCalls";
import type { TOrganizationDataPolicy } from "../../types";

// ── helpers ──────────────────────────────────────────────────────────────────

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function monthsSince(dateStr: string): number {
  const start = new Date(dateStr);
  const now = new Date();
  return Math.max(
    0,
    (now.getFullYear() - start.getFullYear()) * 12 +
      (now.getMonth() - start.getMonth())
  );
}

// ── semáforo ──────────────────────────────────────────────────────────────────

type Light = "green" | "yellow" | "red";

const LIGHT_COLOR: Record<Light, string> = {
  green: "#22c55e",
  yellow: "#eab308",
  red: "#ef4444",
};

function StatusDot({ status }: { status: Light }) {
  const color = LIGHT_COLOR[status];
  return (
    <Box
      style={{
        width: 13,
        height: 13,
        borderRadius: "50%",
        backgroundColor: color,
        boxShadow: `0 0 7px 2px ${color}99`,
        flexShrink: 0,
      }}
    />
  );
}

// ── metric row ────────────────────────────────────────────────────────────────

function Metric({
  label,
  value,
  light,
}: {
  label: string;
  value: string | number;
  light?: Light;
}) {
  return (
    <Group justify="space-between" wrap="nowrap" gap="xs">
      <Text size="xs" c="dimmed" style={{ flex: 1 }}>
        {label}
      </Text>
      <Group gap={6} wrap="nowrap">
        <Text size="xs" fw={600}>
          {value}
        </Text>
        {light && (
          <Box
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              backgroundColor: LIGHT_COLOR[light],
              flexShrink: 0,
            }}
          />
        )}
      </Group>
    </Group>
  );
}

// ── card shell ────────────────────────────────────────────────────────────────

function SummaryCard({
  icon,
  title,
  subtitle,
  status,
  summary,
  loading,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  status: Light;
  summary: string;
  loading: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card withBorder p="md" radius="md" style={{ minHeight: 170 }}>
      <Stack gap="sm">
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs" wrap="nowrap">
            <ThemeIcon size="sm" variant="light" color="violet" radius="sm">
              {icon}
            </ThemeIcon>
            <Stack gap={0}>
              <Text size="xs" fw={700} tt="uppercase" lh={1.2}>
                {title}
              </Text>
              <Text size="xs" c="dimmed" lh={1.2}>
                {subtitle}
              </Text>
            </Stack>
          </Group>
          <StatusDot status={status} />
        </Group>

        {loading ? (
          <Group justify="center" py="xs">
            <Loader size="xs" />
          </Group>
        ) : (
          <Stack gap={6}>{children}</Stack>
        )}

        {!loading && (
          <Text size="xs" c={status === "green" ? "teal" : status === "yellow" ? "yellow" : "red"} fw={500}>
            {summary}
          </Text>
        )}
      </Stack>
    </Card>
  );
}

// ── main component ────────────────────────────────────────────────────────────

interface Props {
  organizationId: string;
  policy: TOrganizationDataPolicy | null;
  policyLoading: boolean;
}

export function GovernanceSummaryCards({
  organizationId,
  policy,
  policyLoading,
}: Props) {
  const { t } = useTranslation();

  // Card 1 — retention
  const [totalMessages, setTotalMessages] = useState<number | null>(null);
  const [totalConversations, setTotalConversations] = useState<number | null>(null);
  const [oldestMonths, setOldestMonths] = useState<number | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Card 2 — business logic
  const [agentCount, setAgentCount] = useState<number | null>(null);
  const [completionCount, setCompletionCount] = useState<number | null>(null);
  const [logicLoading, setLogicLoading] = useState(true);

  // Card 3 — intellectual property
  const [docCount, setDocCount] = useState<number | null>(null);
  const [templateCount, setTemplateCount] = useState<number | null>(null);
  const [ipLoading, setIpLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [stats, oldest] = await Promise.all([
          getConversationStats({ scope: "org" }),
          getConversations({ scope: "org", sortBy: "oldest" }, 0, 1),
        ]);
        setTotalMessages(stats.total_messages);
        setTotalConversations(stats.total_conversations);
        const first = oldest?.results?.[0];
        setOldestMonths(first?.created_at ? monthsSince(first.created_at) : 0);
      } catch {
        // non-critical
      } finally {
        setStatsLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [agents, completions] = await Promise.all([
          getAgents(),
          getUserCompletions(),
        ]);
        const orgAgents = (agents?.agents ?? []).filter(
          (a: any) => a.organization !== null && a.agent_kind !== "platform_assistant"
        );
        setAgentCount(orgAgents.length);
        setCompletionCount(Array.isArray(completions) ? completions.length : 0);
      } catch {
        // non-critical
      } finally {
        setLogicLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [docs, templates] = await Promise.all([
          getDocuments(),
          getDocumentTemplates(organizationId),
        ]);
        const dCount = Array.isArray(docs)
          ? docs.length
          : (docs?.results?.length ?? docs?.count ?? 0);
        setDocCount(dCount);
        setTemplateCount(templates?.templates?.length ?? 0);
      } catch {
        // non-critical
      } finally {
        setIpLoading(false);
      }
    })();
  }, [organizationId]);

  // ── semáforo logic ──────────────────────────────────────────────────────────

  const foreverActive = policy?.deleted_conversation_retention_days === null;

  const retentionStatus: Light =
    statsLoading || policyLoading
      ? "yellow"
      : (totalConversations ?? 0) === 0
      ? "red"
      : foreverActive
      ? "green"
      : "yellow";

  const logicStatus: Light =
    logicLoading
      ? "yellow"
      : (agentCount ?? 0) === 0
      ? "red"
      : (completionCount ?? 0) > 0
      ? "green"
      : "yellow";

  const ipStatus: Light =
    ipLoading
      ? "yellow"
      : (docCount ?? 0) === 0 && (templateCount ?? 0) === 0
      ? "red"
      : (docCount ?? 0) > 0 && (templateCount ?? 0) > 0
      ? "green"
      : "yellow";

  // ── summaries ───────────────────────────────────────────────────────────────

  const retentionSummary =
    retentionStatus === "green"
      ? t("governance-summary-retention-green")
      : retentionStatus === "yellow"
      ? t("governance-summary-retention-yellow")
      : t("governance-summary-retention-red");

  const logicSummary =
    logicStatus === "green"
      ? t("governance-summary-logic-green")
      : logicStatus === "yellow"
      ? t("governance-summary-logic-yellow")
      : t("governance-summary-logic-red");

  const ipSummary =
    ipStatus === "green"
      ? t("governance-summary-ip-green")
      : ipStatus === "yellow"
      ? t("governance-summary-ip-yellow")
      : t("governance-summary-ip-red");

  return (
    <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
      {/* Card 1 – Retención de conocimiento */}
      <SummaryCard
        icon={<IconDatabase size={12} />}
        title={t("governance-card-retention-title")}
        subtitle={t("governance-card-retention-subtitle")}
        status={retentionStatus}
        summary={retentionSummary}
        loading={statsLoading || policyLoading}
      >
        <Metric
          label={t("governance-metric-history")}
          value={
            oldestMonths === null
              ? "—"
              : oldestMonths < 1
              ? t("governance-metric-history-recent")
              : t("governance-metric-months", { count: oldestMonths })
          }
          light={oldestMonths !== null && oldestMonths > 0 ? "green" : "yellow"}
        />
        <Metric
          label={t("governance-metric-forever")}
          value={foreverActive ? t("yes") : t("no")}
          light={foreverActive ? "green" : "yellow"}
        />
        <Metric
          label={t("governance-metric-interactions")}
          value={totalMessages !== null ? formatCount(totalMessages) : "—"}
          light={
            totalMessages === null
              ? undefined
              : totalMessages > 0
              ? "green"
              : "red"
          }
        />
      </SummaryCard>

      {/* Card 2 – Lógica de negocio */}
      <SummaryCard
        icon={<IconBrain size={12} />}
        title={t("governance-card-logic-title")}
        subtitle={t("governance-card-logic-subtitle")}
        status={logicStatus}
        summary={logicSummary}
        loading={logicLoading}
      >
        <Metric
          label={t("governance-metric-agents")}
          value={agentCount !== null ? agentCount : "—"}
          light={
            agentCount === null ? undefined : agentCount > 0 ? "green" : "red"
          }
        />
        <Metric
          label={t("governance-metric-completions")}
          value={completionCount !== null ? formatCount(completionCount) : "—"}
          light={
            completionCount === null
              ? undefined
              : completionCount > 0
              ? "green"
              : "yellow"
          }
        />
      </SummaryCard>

      {/* Card 3 – Propiedad intelectual */}
      <SummaryCard
        icon={<IconFileText size={12} />}
        title={t("governance-card-ip-title")}
        subtitle={t("governance-card-ip-subtitle")}
        status={ipStatus}
        summary={ipSummary}
        loading={ipLoading}
      >
        <Metric
          label={t("governance-metric-documents")}
          value={docCount !== null ? formatCount(docCount) : "—"}
          light={
            docCount === null ? undefined : docCount > 0 ? "green" : "red"
          }
        />
        <Metric
          label={t("governance-metric-templates")}
          value={templateCount !== null ? formatCount(templateCount) : "—"}
          light={
            templateCount === null
              ? undefined
              : templateCount > 0
              ? "green"
              : "yellow"
          }
        />
      </SummaryCard>
    </SimpleGrid>
  );
}
