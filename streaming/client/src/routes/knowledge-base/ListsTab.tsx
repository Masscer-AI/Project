import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  Menu,
  Modal,
  NativeSelect,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconDots,
  IconEdit,
  IconEye,
  IconTrash,
  IconUpload,
} from "@tabler/icons-react";
import {
  deleteOrganizationList,
  getOrganizationList,
  getOrganizationLists,
  getUserOrganizations,
  patchOrganizationList,
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

function isTabularFile(name: string) {
  const lower = name.toLowerCase();
  return (
    lower.endsWith(".csv") || lower.endsWith(".xlsx") || lower.endsWith(".xls")
  );
}

function listNameFromFile(file: File) {
  return file.name.replace(/\.[^.]+$/, "").trim();
}

export function ListsTab({
  filterQuery,
  bindUpload,
  onCount,
}: {
  filterQuery: string;
  bindUpload?: (fn: () => void) => void;
  onCount?: (count: number) => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [orgs, setOrgs] = useState<TOrganization[]>([]);
  const [orgId, setOrgId] = useState<string | null>(
    searchParams.get("organization")
  );
  const [lists, setLists] = useState<TOrganizationList[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [loadingLists, setLoadingLists] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [uploadName, setUploadName] = useState("");
  const [uploadDescription, setUploadDescription] = useState("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  const [activeList, setActiveList] = useState<TOrganizationList | null>(null);
  const [uploadOpened, uploadHandlers] = useDisclosure(false);
  const [deleteModalOpened, deleteModalHandlers] = useDisclosure(false);
  const [editModalOpened, editModalHandlers] = useDisclosure(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

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
      setLists(rows ?? []);
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
        const list = await getUserOrganizations();
        if (cancelled) return;
        const orgList = Array.isArray(list) ? list : [];
        setOrgs(orgList);
        if (orgList.length > 0) {
          setOrgId((current) => {
            if (current && orgList.some((o) => String(o.id) === current)) {
              return current;
            }
            const fromUrl = searchParams.get("organization");
            const match = fromUrl
              ? orgList.find((o) => String(o.id) === fromUrl)
              : undefined;
            return String(match?.id ?? orgList[0].id);
          });
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
    onCount?.(lists.length);
  }, [lists.length, onCount]);

  useEffect(() => {
    bindUpload?.(() => uploadHandlers.open());
  }, [bindUpload, uploadHandlers.open]);

  useEffect(() => {
    if (!orgId) return;
    const needsPoll = lists.some((row) => isImportInProgress(row.import_status));
    if (!needsPoll) return;
    const timer = window.setInterval(async () => {
      try {
        const { lists: fresh } = await getOrganizationLists(orgId);
        setLists(fresh ?? []);
      } catch {
        /* ignore poll errors */
      }
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [orgId, lists]);

  const handleFilePicked = (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    if (!isTabularFile(file.name)) {
      toast.error(t("org-list-file-type-error"));
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setPendingFile(file);
    setUploadName(listNameFromFile(file));
  };

  const handleUpload = async () => {
    if (!orgId || !pendingFile) return;
    const name = uploadName.trim();
    if (!name) {
      toast.error(t("org-list-name-required"));
      return;
    }
    setUploading(true);
    const toastId = toast.loading(t("org-list-uploading"));
    try {
      const fd = new FormData();
      fd.append("name", name);
      fd.append("description", uploadDescription);
      fd.append("file", pendingFile);
      await uploadOrganizationList(orgId, fd);
      toast.success(t("org-list-upload-started"));
      setUploadName("");
      setUploadDescription("");
      setPendingFile(null);
      uploadHandlers.close();
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

  const openEdit = (row: TOrganizationList) => {
    setActiveList(row);
    setEditName(row.name);
    setEditDescription(row.description || "");
    editModalHandlers.open();
  };

  const saveEdit = async () => {
    if (!orgId || !activeList) return;
    const name = editName.trim();
    if (!name) {
      toast.error(t("org-list-name-required"));
      return;
    }
    setSavingEdit(true);
    const toastId = toast.loading(t("saving"));
    try {
      const { list } = await patchOrganizationList(orgId, activeList.id, {
        name,
        description: editDescription,
      });
      setLists((prev) => prev.map((x) => (x.id === list.id ? list : x)));
      toast.success(t("org-list-saved"));
      editModalHandlers.close();
    } catch {
      toast.error(t("org-list-save-error"));
    } finally {
      toast.dismiss(toastId);
      setSavingEdit(false);
    }
  };

  const openPreview = (row: TOrganizationList) => {
    if (!orgId) return;
    navigate(
      `/knowledge-base/lists/${row.id}?organization=${encodeURIComponent(orgId)}`
    );
  };

  const triggerReplace = (row: TOrganizationList) => {
    setActiveList(row);
    replaceInputRef.current?.click();
  };

  const handleReplaceFile = async (files: FileList | null) => {
    if (!orgId || !activeList || !files?.length) return;
    const file = files[0];
    if (!isTabularFile(file.name)) {
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

      {orgs.length > 1 && (
        <NativeSelect
          label={t("organization-for-lists")}
          data={orgSelectData}
          value={orgId ?? ""}
          onChange={(e) => {
            const v = e.currentTarget.value;
            setOrgId(v || null);
            const next = new URLSearchParams(searchParams);
            if (v) next.set("organization", v);
            else next.delete("organization");
            setSearchParams(next, { replace: true });
          }}
          size="sm"
          w={280}
        />
      )}

      <Text size="sm" c="dimmed">
        {t("org-lists-tab-description")}
      </Text>

      <Modal
        opened={uploadOpened}
        onClose={uploadHandlers.close}
        title={t("org-list-upload-new")}
      >
        <Stack gap="sm">
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
          <input
            ref={fileInputRef}
            type="file"
            accept={TABULAR_ACCEPT}
            style={{ display: "none" }}
            onChange={(e) => handleFilePicked(e.currentTarget.files)}
          />
          <Group>
            <Button
              variant="default"
              leftSection={<IconUpload size={16} />}
              onClick={() => fileInputRef.current?.click()}
            >
              {t("org-list-choose-file")}
            </Button>
            {pendingFile ? (
              <Text size="sm" c="dimmed">
                {pendingFile.name}
              </Text>
            ) : null}
          </Group>
          <Group justify="flex-end">
            <Button variant="default" onClick={uploadHandlers.close}>
              {t("cancel")}
            </Button>
            <Button
              loading={uploading}
              disabled={!pendingFile}
              onClick={handleUpload}
            >
              {t("upload")}
            </Button>
          </Group>
        </Stack>
      </Modal>

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
        <Table highlightOnHover verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t("kb-col-list")}</Table.Th>
              <Table.Th ta="right">{t("kb-col-rows")}</Table.Th>
              <Table.Th>{t("kb-col-status")}</Table.Th>
              <Table.Th w={48} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filteredLists.map((row) => {
              const ext = (row.original_filename || "").toLowerCase();
              const kind = ext.endsWith(".csv")
                ? { label: "CSV", color: "teal" }
                : { label: "XLS", color: "green" };
              return (
                <Table.Tr
                  key={row.id}
                  style={{
                    cursor: row.import_status === "succeeded" ? "pointer" : undefined,
                  }}
                  onClick={() => {
                    if (row.import_status === "succeeded") openPreview(row);
                  }}
                >
                  <Table.Td>
                    <Group gap="sm" wrap="nowrap">
                      <Box
                        w={36}
                        h={36}
                        style={{
                          borderRadius: 8,
                          background: `var(--mantine-color-${kind.color}-light)`,
                          color: `var(--mantine-color-${kind.color}-6)`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 11,
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {kind.label}
                      </Box>
                      <Box style={{ minWidth: 0 }}>
                        <Text fw={600} lineClamp={1}>
                          {row.name}
                        </Text>
                        <Text size="sm" c="dimmed" lineClamp={1}>
                          {row.original_filename}
                        </Text>
                        {row.import_status === "failed" && row.import_error ? (
                          <Text size="xs" c="red" lineClamp={1}>
                            {row.import_error}
                          </Text>
                        ) : null}
                      </Box>
                    </Group>
                  </Table.Td>
                  <Table.Td ta="right">{row.record_count}</Table.Td>
                  <Table.Td>
                    <Badge
                      color={importStatusColor(row.import_status)}
                      variant="light"
                      size="sm"
                      styles={{ label: { textTransform: "none" } }}
                    >
                      {t(`org-list-import-status-${row.import_status}`)}
                    </Badge>
                  </Table.Td>
                  <Table.Td onClick={(e) => e.stopPropagation()}>
                    <Menu position="bottom-end">
                      <Menu.Target>
                        <ActionIcon variant="subtle" color="gray" aria-label={t("edit")}>
                          <IconDots size={16} />
                        </ActionIcon>
                      </Menu.Target>
                      <Menu.Dropdown>
                        <Menu.Item
                          leftSection={<IconEdit size={14} />}
                          onClick={() => openEdit(row)}
                        >
                          {t("edit")}
                        </Menu.Item>
                        <Menu.Item
                          leftSection={<IconEye size={14} />}
                          disabled={row.import_status !== "succeeded"}
                          onClick={() => openPreview(row)}
                        >
                          {t("org-list-preview")}
                        </Menu.Item>
                        <Menu.Item
                          leftSection={<IconUpload size={14} />}
                          onClick={() => triggerReplace(row)}
                        >
                          {t("org-list-replace-file")}
                        </Menu.Item>
                        <Menu.Item
                          color="red"
                          leftSection={<IconTrash size={14} />}
                          onClick={() => openDelete(row)}
                        >
                          {t("delete")}
                        </Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
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
        opened={editModalOpened}
        onClose={editModalHandlers.close}
        title={t("org-list-edit-title")}
      >
        <Stack gap="sm">
          <TextInput
            label={t("org-list-name")}
            value={editName}
            onChange={(e) => setEditName(e.currentTarget.value)}
          />
          <Textarea
            label={t("org-list-description")}
            value={editDescription}
            onChange={(e) => setEditDescription(e.currentTarget.value)}
            autosize
            minRows={2}
          />
          <Group justify="flex-end" mt="xs">
            <Button variant="default" onClick={editModalHandlers.close}>
              {t("cancel")}
            </Button>
            <Button loading={savingEdit} onClick={saveEdit}>
              {t("save")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
