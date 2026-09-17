import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  NativeSelect,
  ScrollArea,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconEye,
  IconList,
  IconTrash,
  IconUpload,
} from "@tabler/icons-react";
import {
  deleteOrganizationList,
  getOrganizationList,
  getOrganizationListRecords,
  getOrganizationLists,
  getUserOrganizations,
  replaceOrganizationListFile,
  uploadOrganizationList,
} from "../../modules/apiCalls";
import type { TOrganization, TOrganizationList } from "../../types";

const POLL_MS = 4000;
const TABULAR_ACCEPT = ".csv,.xlsx,.xls";

function importStatusColor(
  status: TOrganizationList["import_status"]
): string {
  if (status === "succeeded") return "green";
  if (status === "failed") return "red";
  if (status === "processing") return "blue";
  return "yellow";
}

function isImportInProgress(status: TOrganizationList["import_status"]) {
  return status === "pending" || status === "processing";
}

export function ListsTab({ filterQuery }: { filterQuery: string }) {
  const { t } = useTranslation();
  const [orgs, setOrgs] = useState<TOrganization[]>([]);
  const [orgId, setOrgId] = useState<string | null>(null);
  const [lists, setLists] = useState<TOrganizationList[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [loadingLists, setLoadingLists] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [uploadName, setUploadName] = useState("");
  const [uploadDescription, setUploadDescription] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  const [activeList, setActiveList] = useState<TOrganizationList | null>(null);
  const [deleteModalOpened, deleteModalHandlers] = useDisclosure(false);
  const [previewModalOpened, previewModalHandlers] = useDisclosure(false);
  const [previewRows, setPreviewRows] = useState<
    { position: number; data: Record<string, string> }[]
  >([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  const orgSelectData = useMemo(
    () =>
      orgs.map((o) => ({
        value: String(o.id),
        label: o.name,
      })),
    [orgs]
  );

  const filteredLists = useMemo(() => {
    const q = filterQuery.trim().toLowerCase();
    if (!q) return lists;
    return lists.filter(
      (row) =>
        row.name.toLowerCase().includes(q) ||
        (row.description || "").toLowerCase().includes(q) ||
        (row.original_filename || "").toLowerCase().includes(q)
    );
  }, [lists, filterQuery]);

  const loadLists = useCallback(async (id: string) => {
    setLoadingLists(true);
    try {
      const { lists: rows } = await getOrganizationLists(id);
      setLists(rows);
    } catch {
      toast.error(t("org-lists-load-error"));
      setLists([]);
    } finally {
      setLoadingLists(false);
    }
  }, [t]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingOrgs(true);
      try {
        const { organizations } = await getUserOrganizations();
        if (cancelled) return;
        setOrgs(organizations);
        if (organizations.length > 0) {
          setOrgId(String(organizations[0].id));
        }
      } catch {
        if (!cancelled) toast.error(t("org-lists-load-error"));
      } finally {
        if (!cancelled) setLoadingOrgs(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t]);

  useEffect(() => {
    if (orgId) loadLists(orgId);
  }, [orgId, loadLists]);

  useEffect(() => {
    if (!orgId) return;
    const needsPoll = lists.some((row) => isImportInProgress(row.import_status));
    if (!needsPoll) return;
    const timer = window.setInterval(async () => {
      try {
        const { lists: fresh } = await getOrganizationLists(orgId);
        setLists(fresh);
      } catch {
        /* ignore poll errors */
      }
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [orgId, lists]);

  const handleUpload = async (files: FileList | null) => {
    if (!orgId || !files?.length) return;
    const name = uploadName.trim();
    if (!name) {
      toast.error(t("org-list-name-required"));
      return;
    }
    setUploading(true);
    const toastId = toast.loading(t("org-list-uploading"));
    try {
      for (const file of Array.from(files)) {
        const lower = file.name.toLowerCase();
        if (
          !lower.endsWith(".csv") &&
          !lower.endsWith(".xlsx") &&
          !lower.endsWith(".xls")
        ) {
          toast.error(t("org-list-file-type-error"));
          continue;
        }
        const fd = new FormData();
        fd.append("name", name);
        fd.append("description", uploadDescription);
        fd.append("file", file);
        await uploadOrganizationList(orgId, fd);
      }
      toast.success(t("org-list-upload-started"));
      setUploadName("");
      setUploadDescription("");
      await loadLists(orgId);
    } catch {
      toast.error(t("org-list-upload-error"));
    } finally {
      toast.dismiss(toastId);
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const openDelete = (row: TOrganizationList) => {
    setActiveList(row);
    deleteModalHandlers.open();
  };

  const confirmDelete = async () => {
    if (!orgId || !activeList) return;
    const toastId = toast.loading(t("deleting"));
    try {
      await deleteOrganizationList(orgId, activeList.id);
      toast.success(t("org-list-deleted"));
      deleteModalHandlers.close();
      await loadLists(orgId);
    } catch {
      toast.error(t("org-list-delete-error"));
    } finally {
      toast.dismiss(toastId);
    }
  };

  const openPreview = async (row: TOrganizationList) => {
    if (!orgId) return;
    setActiveList(row);
    previewModalHandlers.open();
    setPreviewLoading(true);
    try {
      const { records } = await getOrganizationListRecords(orgId, row.id, 1, 20);
      setPreviewRows(
        records.map((r) => ({ position: r.position, data: r.data || {} }))
      );
    } catch {
      toast.error(t("org-list-preview-error"));
      setPreviewRows([]);
    } finally {
      setPreviewLoading(false);
    }
  };

  const triggerReplace = (row: TOrganizationList) => {
    setActiveList(row);
    replaceInputRef.current?.click();
  };

  const handleReplaceFile = async (files: FileList | null) => {
    if (!orgId || !activeList || !files?.length) return;
    const file = files[0];
    const lower = file.name.toLowerCase();
    if (
      !lower.endsWith(".csv") &&
      !lower.endsWith(".xlsx") &&
      !lower.endsWith(".xls")
    ) {
      toast.error(t("org-list-file-type-error"));
      return;
    }
    const toastId = toast.loading(t("org-list-replace-uploading"));
    try {
      const fd = new FormData();
      fd.append("file", file);
      await replaceOrganizationListFile(orgId, activeList.id, fd);
      toast.success(t("org-list-replace-started"));
      await loadLists(orgId);
      const { list } = await getOrganizationList(orgId, activeList.id);
      setActiveList(list);
    } catch {
      toast.error(t("org-list-replace-error"));
    } finally {
      toast.dismiss(toastId);
      if (replaceInputRef.current) replaceInputRef.current.value = "";
    }
  };

  if (loadingOrgs) {
    return (
      <Stack align="center" py="xl">
        <Loader color="violet" />
      </Stack>
    );
  }

  if (orgs.length === 0) {
    return (
      <Card withBorder p="lg">
        <Text c="dimmed" ta="center">
          {t("org-lists-no-organization")}
        </Text>
      </Card>
    );
  }

  return (
    <Stack gap="md">
      <input
        ref={replaceInputRef}
        type="file"
        accept={TABULAR_ACCEPT}
        style={{ display: "none" }}
        onChange={(e) => handleReplaceFile(e.currentTarget.files)}
      />

      <Group align="flex-end" wrap="wrap">
        <NativeSelect
          label={t("organization-for-lists")}
          data={orgSelectData}
          value={orgId ?? ""}
          onChange={(e) => {
            const v = e.currentTarget.value;
            setOrgId(v || null);
          }}
          size="sm"
          w={280}
        />
      </Group>

      <Text size="sm" c="dimmed">
        {t("org-lists-tab-description")}
      </Text>

      <Card withBorder p="md">
        <Stack gap="sm">
          <Title order={5}>{t("org-list-upload-new")}</Title>
          <Group grow align="flex-start" wrap="wrap">
            <TextInput
              label={t("org-list-name")}
              placeholder={t("org-list-name-placeholder")}
              value={uploadName}
              onChange={(e) => setUploadName(e.currentTarget.value)}
              size="sm"
            />
            <Textarea
              label={t("org-list-description")}
              placeholder={t("optional")}
              value={uploadDescription}
              onChange={(e) => setUploadDescription(e.currentTarget.value)}
              size="sm"
              autosize
              minRows={1}
            />
          </Group>
          <Group>
            <input
              ref={fileInputRef}
              type="file"
              accept={TABULAR_ACCEPT}
              style={{ display: "none" }}
              onChange={(e) => handleUpload(e.currentTarget.files)}
            />
            <Button
              leftSection={<IconUpload size={16} />}
              loading={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {t("org-list-choose-file")}
            </Button>
          </Group>
        </Stack>
      </Card>

      {loadingLists ? (
        <Stack align="center" py="lg">
          <Loader color="violet" size="sm" />
        </Stack>
      ) : filteredLists.length === 0 ? (
        <Card withBorder p="lg">
          <Text c="dimmed" ta="center">
            {t("org-lists-empty")}
          </Text>
        </Card>
      ) : (
        <Stack gap="sm">
          {filteredLists.map((row) => (
            <Card key={row.id} withBorder p="md">
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
                  <Group gap="xs" wrap="wrap">
                    <IconList size={18} />
                    <Text fw={600} truncate>
                      {row.name}
                    </Text>
                    <Badge color={importStatusColor(row.import_status)} size="sm">
                      {t(`org-list-import-status-${row.import_status}`)}
                    </Badge>
                  </Group>
                  {row.description ? (
                    <Text size="sm" c="dimmed">
                      {row.description}
                    </Text>
                  ) : null}
                  <Text size="xs" c="dimmed">
                    {row.original_filename} · {row.record_count}{" "}
                    {t("org-list-records-label")}
                  </Text>
                  {row.import_status === "failed" && row.import_error ? (
                    <Text size="xs" c="red">
                      {row.import_error}
                    </Text>
                  ) : null}
                </Stack>
                <Group gap="xs" wrap="nowrap">
                  <Tooltip label={t("org-list-preview")}>
                    <ActionIcon
                      variant="subtle"
                      color="gray"
                      disabled={row.import_status !== "succeeded"}
                      onClick={() => openPreview(row)}
                    >
                      <IconEye size={18} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label={t("org-list-replace-file")}>
                    <ActionIcon
                      variant="subtle"
                      color="gray"
                      onClick={() => triggerReplace(row)}
                    >
                      <IconUpload size={18} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label={t("delete")}>
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      onClick={() => openDelete(row)}
                    >
                      <IconTrash size={18} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
              </Group>
            </Card>
          ))}
        </Stack>
      )}

      <Modal
        opened={deleteModalOpened}
        onClose={deleteModalHandlers.close}
        title={t("org-list-delete-title")}
      >
        <Text size="sm" mb="md">
          {t("org-list-delete-body", { name: activeList?.name ?? "" })}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={deleteModalHandlers.close}>
            {t("cancel")}
          </Button>
          <Button color="red" onClick={confirmDelete}>
            {t("delete")}
          </Button>
        </Group>
      </Modal>

      <Modal
        opened={previewModalOpened}
        onClose={previewModalHandlers.close}
        title={t("org-list-preview-title", { name: activeList?.name ?? "" })}
        size="lg"
      >
        {previewLoading ? (
          <Loader color="violet" size="sm" />
        ) : previewRows.length === 0 ? (
          <Text c="dimmed">{t("org-list-preview-empty")}</Text>
        ) : (
          <ScrollArea h={320}>
            <Stack gap="xs">
              {previewRows.map((row) => (
                <Card key={row.position} withBorder p="xs">
                  <Text size="xs" c="dimmed" mb={4}>
                    #{row.position}
                  </Text>
                  <Text size="sm" style={{ fontFamily: "monospace" }}>
                    {JSON.stringify(row.data)}
                  </Text>
                </Card>
              ))}
            </Stack>
          </ScrollArea>
        )}
      </Modal>
    </Stack>
  );
}
