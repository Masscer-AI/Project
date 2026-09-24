import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconEdit,
  IconEye,
  IconList,
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

export function ListsTab({ filterQuery }: { filterQuery: string }) {
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

      <Group align="flex-end" wrap="wrap">
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
              onChange={(e) => handleFilePicked(e.currentTarget.files)}
            />
            <Button
              variant="default"
              leftSection={<IconUpload size={16} />}
              onClick={() => fileInputRef.current?.click()}
            >
              {t("org-list-choose-file")}
            </Button>
            <Button
              loading={uploading}
              disabled={!pendingFile}
              onClick={handleUpload}
            >
              {t("upload")}
            </Button>
            {pendingFile ? (
              <Text size="sm" c="dimmed">
                {pendingFile.name}
              </Text>
            ) : null}
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
                    <Text
                      fw={600}
                      truncate
                      style={
                        row.import_status === "succeeded"
                          ? { cursor: "pointer" }
                          : undefined
                      }
                      onClick={() => {
                        if (row.import_status === "succeeded") {
                          openPreview(row);
                        }
                      }}
                    >
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
                  <Tooltip label={t("edit")}>
                    <ActionIcon
                      variant="subtle"
                      color="gray"
                      onClick={() => openEdit(row)}
                    >
                      <IconEdit size={18} />
                    </ActionIcon>
                  </Tooltip>
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
