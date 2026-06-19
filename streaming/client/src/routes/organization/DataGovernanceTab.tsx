import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  Loader,
  NativeSelect,
  NumberInput,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconDownload, IconPackageExport } from "@tabler/icons-react";
import {
  createDataExportJob,
  downloadDataExport,
  getOrganizationDataPolicy,
  listDataExportJobs,
  updateOrganizationDataPolicy,
} from "../../modules/apiCalls";
import { TDataExportJob, TOrganizationDataPolicy } from "../../types";
import { GovernanceSummaryCards } from "./GovernanceSummaryCards";

type Props = {
  organizationId: string;
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function formatBytes(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusColor(
  status: TDataExportJob["status"]
): "gray" | "blue" | "green" | "red" | "yellow" {
  switch (status) {
    case "ready":
      return "green";
    case "failed":
      return "red";
    case "processing":
    case "pending":
      return "blue";
    case "expired":
      return "yellow";
    default:
      return "gray";
  }
}

export function DataGovernanceTab({ organizationId }: Props) {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const highlightExportId = searchParams.get("export");

  const [policy, setPolicy] = useState<TOrganizationDataPolicy | null>(null);
  const [deletedDays, setDeletedDays] = useState<string | number>("");
  const [attachmentDays, setAttachmentDays] = useState<string | number>("");
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [loadingPolicy, setLoadingPolicy] = useState(true);

  const [jobs, setJobs] = useState<TDataExportJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [submittingExport, setSubmittingExport] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const [dateFrom, setDateFrom] = useState(daysAgoIso(30));
  const [dateTo, setDateTo] = useState(todayIso());
  const [exportConversations, setExportConversations] = useState(true);
  const [includeAttachments, setIncludeAttachments] = useState(false);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [exportAgents, setExportAgents] = useState(true);
  const [exportCompletions, setExportCompletions] = useState(false);
  const [exportDocuments, setExportDocuments] = useState(false);
  const [includeDocumentFiles, setIncludeDocumentFiles] = useState(false);
  const [exportTemplates, setExportTemplates] = useState(false);
  const [notifyVia, setNotifyVia] = useState<"app" | "email" | "both">("both");

  const loadPolicy = useCallback(async () => {
    try {
      setLoadingPolicy(true);
      const data = await getOrganizationDataPolicy(organizationId);
      setPolicy(data);
      setDeletedDays(data.deleted_conversation_retention_days ?? "");
      setAttachmentDays(data.attachment_retention_days ?? "");
    } catch (e) {
      console.error(e);
      toast.error(t("data-governance-load-error"));
    } finally {
      setLoadingPolicy(false);
    }
  }, [organizationId, t]);

  const loadJobs = useCallback(async () => {
    try {
      setLoadingJobs(true);
      const data = await listDataExportJobs(organizationId);
      setJobs(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingJobs(false);
    }
  }, [organizationId]);

  useEffect(() => {
    loadPolicy();
    loadJobs();
  }, [loadPolicy, loadJobs]);

  useEffect(() => {
    const onReady = () => loadJobs();
    window.addEventListener("masscer:data-export-ready", onReady);
    return () => window.removeEventListener("masscer:data-export-ready", onReady);
  }, [loadJobs]);

  useEffect(() => {
    const pending = jobs.some(
      (j) => j.status === "pending" || j.status === "processing"
    );
    if (!pending) return;
    const id = window.setInterval(loadJobs, 5000);
    return () => window.clearInterval(id);
  }, [jobs, loadJobs]);

  const handleSavePolicy = async () => {
    setSavingPolicy(true);
    try {
      const payload = {
        deleted_conversation_retention_days:
          deletedDays === "" ? null : Number(deletedDays),
        attachment_retention_days:
          attachmentDays === "" ? null : Number(attachmentDays),
      };
      const updated = await updateOrganizationDataPolicy(
        organizationId,
        payload
      );
      setPolicy(updated);
      toast.success(t("data-governance-policy-saved"));
    } catch (e) {
      console.error(e);
      toast.error(t("data-governance-policy-save-error"));
    } finally {
      setSavingPolicy(false);
    }
  };

  const handleCreateExport = async () => {
    if (
      !exportConversations &&
      !exportAgents &&
      !exportCompletions &&
      !exportDocuments &&
      !exportTemplates
    ) {
      toast.error(t("data-governance-export-category-required"));
      return;
    }
    setSubmittingExport(true);
    try {
      await createDataExportJob(organizationId, {
        notify_via: notifyVia,
        manifest: {
          date_from: dateFrom,
          date_to: dateTo,
          categories: {
            conversations: {
              enabled: exportConversations,
              include_attachments: includeAttachments,
              include_deleted: includeDeleted,
            },
            agents: { enabled: exportAgents },
            completions: { enabled: exportCompletions },
            documents: {
              enabled: exportDocuments,
              include_files: includeDocumentFiles,
            },
            document_templates: { enabled: exportTemplates },
          },
        },
      });
      toast.success(t("data-governance-export-started"));
      await loadJobs();
    } catch (e) {
      console.error(e);
      toast.error(t("data-governance-export-error"));
    } finally {
      setSubmittingExport(false);
    }
  };

  const handleDownload = async (jobId: string) => {
    setDownloadingId(jobId);
    try {
      await downloadDataExport(organizationId, jobId);
      await loadJobs();
    } catch (e) {
      console.error(e);
      toast.error(t("data-governance-download-error"));
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <Stack gap="lg">
      <GovernanceSummaryCards
        organizationId={organizationId}
        policy={policy}
        policyLoading={loadingPolicy}
      />

      <Card withBorder p="lg">
        <Title order={4} mb="xs">
          {t("data-governance-retention-title")}
        </Title>
        <Text size="sm" c="dimmed" mb="md">
          {t("data-governance-retention-description")}
        </Text>
        {loadingPolicy ? (
          <Loader size="sm" />
        ) : (
          <Stack gap="md">
            <NumberInput
              label={t("data-governance-deleted-conversations-days")}
              description={t("data-governance-keep-forever-hint")}
              placeholder={t("data-governance-forever-placeholder")}
              min={0}
              value={deletedDays}
              onChange={setDeletedDays}
            />
            <NumberInput
              label={t("data-governance-attachment-days")}
              description={t("data-governance-attachment-min-hint")}
              placeholder={t("data-governance-forever-placeholder")}
              min={7}
              value={attachmentDays}
              onChange={setAttachmentDays}
            />
            <Group>
              <Button loading={savingPolicy} onClick={handleSavePolicy}>
                {t("save")}
              </Button>
              {policy?.updated_at && (
                <Text size="xs" c="dimmed">
                  {t("data-governance-last-updated", {
                    date: new Date(policy.updated_at).toLocaleString(),
                  })}
                </Text>
              )}
            </Group>
          </Stack>
        )}
      </Card>

      <Card withBorder p="lg">
        <Group justify="space-between" wrap="wrap" gap="xl" align="flex-start">
          {/* Left: description */}
          <Stack gap="xs" style={{ flex: 1, minWidth: 200 }}>
            <Title order={4}>{t("data-governance-export-title")}</Title>
            <Text size="sm" c="dimmed">{t("data-governance-export-description")}</Text>
            <Stack gap={4} mt="xs">
              <Group gap="xs">
                <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
                <Text size="xs" c="dimmed">→</Text>
                <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
              </Group>
            </Stack>
          </Stack>

          {/* Right: categories + button */}
          <Stack gap="sm" style={{ flex: 1, minWidth: 220 }}>
            <Stack gap={6}>
              <Checkbox label={t("data-governance-export-conversations")} checked={exportConversations} onChange={(e) => setExportConversations(e.currentTarget.checked)} />
              {exportConversations && (
                <Stack gap={4} pl="md">
                  <Checkbox label={t("data-governance-include-attachments")} checked={includeAttachments} onChange={(e) => setIncludeAttachments(e.currentTarget.checked)} />
                  <Checkbox label={t("data-governance-include-deleted")} checked={includeDeleted} onChange={(e) => setIncludeDeleted(e.currentTarget.checked)} />
                </Stack>
              )}
              <Checkbox label={t("data-governance-export-agents")} checked={exportAgents} onChange={(e) => setExportAgents(e.currentTarget.checked)} />
              <Checkbox label={t("data-governance-export-completions")} checked={exportCompletions} onChange={(e) => setExportCompletions(e.currentTarget.checked)} />
              <Checkbox label={t("data-governance-export-documents")} checked={exportDocuments} onChange={(e) => setExportDocuments(e.currentTarget.checked)} />
              {exportDocuments && (
                <Checkbox pl="md" label={t("data-governance-include-document-files")} checked={includeDocumentFiles} onChange={(e) => setIncludeDocumentFiles(e.currentTarget.checked)} />
              )}
              <Checkbox label={t("data-governance-export-templates")} checked={exportTemplates} onChange={(e) => setExportTemplates(e.currentTarget.checked)} />
            </Stack>
            <NativeSelect
              size="xs"
              value={notifyVia}
              onChange={(e) => setNotifyVia(e.currentTarget.value as typeof notifyVia)}
              data={[
                { value: "both", label: t("data-governance-notify-both") },
                { value: "app", label: t("data-governance-notify-app") },
                { value: "email", label: t("data-governance-notify-email") },
              ]}
            />
            <Button
              loading={submittingExport}
              onClick={handleCreateExport}
              leftSection={<IconPackageExport size={16} />}
              fullWidth
            >
              {t("data-governance-request-export")}
            </Button>
          </Stack>
        </Group>
      </Card>

      <Card withBorder p="lg">
        <Title order={4} mb="md">
          {t("data-governance-export-jobs")}
        </Title>
        {loadingJobs ? (
          <Loader size="sm" />
        ) : jobs.length === 0 ? (
          <Text c="dimmed" size="sm">
            {t("data-governance-no-exports")}
          </Text>
        ) : (
          <Stack gap="sm">
            {jobs.map((job) => (
              <Card
                key={job.id}
                withBorder
                p="sm"
                style={
                  highlightExportId === job.id
                    ? { borderColor: "var(--mantine-color-violet-6)" }
                    : undefined
                }
              >
                <Group justify="space-between" wrap="nowrap">
                  <Stack gap={2}>
                    <Group gap="xs">
                      <Badge color={statusColor(job.status)} size="sm">
                        {job.status}
                      </Badge>
                      <Text size="xs" c="dimmed">
                        {job.created_at
                          ? new Date(job.created_at).toLocaleString()
                          : ""}
                      </Text>
                      {job.file_size_bytes != null && (
                        <Text size="xs" c="dimmed">
                          {formatBytes(job.file_size_bytes)}
                        </Text>
                      )}
                    </Group>
                    {job.error_message && (
                      <Text size="xs" c="red">
                        {job.error_message}
                      </Text>
                    )}
                    {job.expires_at && job.status === "ready" && (
                      <Text size="xs" c="dimmed">
                        {t("data-governance-expires", {
                          date: new Date(job.expires_at).toLocaleString(),
                        })}
                      </Text>
                    )}
                  </Stack>
                  {job.status === "ready" && (
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconDownload size={14} />}
                      loading={downloadingId === job.id}
                      onClick={() => handleDownload(job.id)}
                    >
                      {t("download")}
                    </Button>
                  )}
                </Group>
              </Card>
            ))}
          </Stack>
        )}
      </Card>
    </Stack>
  );
}
