import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Button,
  Divider,
  Group,
  Modal,
  MultiSelect,
  NativeSelect,
  Stack,
  Text,
} from "@mantine/core";
import { IconDownload, IconLink, IconUser, IconUsers } from "@tabler/icons-react";
import { DocumentFileIcon, getDocumentFileMeta } from "../../modules/documentFileMeta";
import {
  getGalleryItem,
  getOrganizationRoles,
  getUserOrganizations,
  TAttachmentVisibility,
  TGalleryItem,
  updateGalleryItemVisibility,
} from "../../modules/apiCalls";
import { TOrganizationRole } from "../../types";

export function visibilityLabelKey(
  visibility?: TAttachmentVisibility
): string {
  if (visibility === "organization") return "gallery-visibility-organization";
  if (visibility === "roles") return "gallery-visibility-roles";
  if (visibility === "link") return "gallery-visibility-link";
  return "gallery-visibility-personal";
}

export function VisibilityGlyph({
  visibility,
  size = 16,
}: {
  visibility?: TAttachmentVisibility;
  size?: number;
}) {
  if (visibility === "organization" || visibility === "roles") {
    return <IconUsers size={size} />;
  }
  if (visibility === "link") {
    return <IconLink size={size} />;
  }
  return <IconUser size={size} />;
}

function formatCreatedAt(iso: string | null | undefined, locale: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

function useAttachmentVisibilityEditor(
  opened: boolean,
  attachmentId: string | undefined,
  initialItem: TGalleryItem | null | undefined
) {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [item, setItem] = useState<TGalleryItem | null>(initialItem ?? null);
  const [editVisibility, setEditVisibility] = useState<TAttachmentVisibility>(
    initialItem?.visibility || "personal"
  );
  const [editRoleIds, setEditRoleIds] = useState<string[]>(
    (initialItem?.belongs_to?.roles || []).map((r) => r.id)
  );
  const [orgRoles, setOrgRoles] = useState<TOrganizationRole[]>([]);
  const [hasOrg, setHasOrg] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    if (!opened || !attachmentId) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setLoadError(false);
      try {
        const [detail, orgs] = await Promise.all([
          getGalleryItem(attachmentId),
          getUserOrganizations(),
        ]);
        if (cancelled) return;
        const next = detail.item;
        setItem(next);
        setEditVisibility(next.visibility || "personal");
        setEditRoleIds((next.belongs_to?.roles || []).map((r) => r.id));
        const org = orgs[0];
        setHasOrg(Boolean(org));
        if (!org) {
          setOrgRoles([]);
          return;
        }
        const roles = await getOrganizationRoles(org.id);
        if (!cancelled) setOrgRoles(roles.filter((r) => r.enabled));
      } catch {
        if (!cancelled) setLoadError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [opened, attachmentId]);

  const visibilityOptions = [
    { value: "personal", label: t("gallery-visibility-personal") },
    ...(hasOrg
      ? [
          {
            value: "organization",
            label: t("gallery-visibility-organization"),
          },
          { value: "roles", label: t("gallery-visibility-roles") },
        ]
      : []),
    ...(editVisibility === "link"
      ? [{ value: "link", label: t("gallery-visibility-link") }]
      : []),
  ];

  const canManage = Boolean(item && item.can_manage !== false && !loadError);

  const save = async (onSaved?: (item: TGalleryItem) => void) => {
    if (!attachmentId) return;
    if (editVisibility === "roles" && editRoleIds.length === 0) {
      toast.error(t("document-visibility-roles-required"));
      return false;
    }
    if (!canManage) {
      toast.error(t("gallery-visibility-forbidden"));
      return false;
    }
    setSaving(true);
    try {
      const res = await updateGalleryItemVisibility(attachmentId, {
        visibility: editVisibility,
        role_ids: editVisibility === "roles" ? editRoleIds : [],
      });
      toast.success(t("gallery-visibility-updated"));
      setItem(res.item);
      onSaved?.(res.item);
      return true;
    } catch {
      toast.error(t("gallery-visibility-update-error"));
      return false;
    } finally {
      setSaving(false);
    }
  };

  return {
    saving,
    loading,
    item,
    editVisibility,
    setEditVisibility,
    editRoleIds,
    setEditRoleIds,
    orgRoles,
    visibilityOptions,
    canManage,
    loadError,
    save,
  };
}

function VisibilityFields({
  editor,
}: {
  editor: ReturnType<typeof useAttachmentVisibilityEditor>;
}) {
  const { t } = useTranslation();
  return (
    <Stack gap="sm">
      <NativeSelect
        size="sm"
        label={t("gallery-visibility")}
        value={editor.editVisibility}
        disabled={editor.loading || !editor.canManage}
        onChange={(e) => {
          const val = e.currentTarget.value as TAttachmentVisibility;
          editor.setEditVisibility(val);
          if (val !== "roles") editor.setEditRoleIds([]);
        }}
        data={editor.visibilityOptions}
      />
      {editor.editVisibility === "roles" && (
        <MultiSelect
          size="sm"
          label={t("document-visibility-select-roles")}
          placeholder={t("document-visibility-select-roles")}
          data={editor.orgRoles.map((r) => ({ value: r.id, label: r.name }))}
          value={editor.editRoleIds}
          onChange={editor.setEditRoleIds}
          searchable
          disabled={editor.loading || !editor.canManage}
        />
      )}
    </Stack>
  );
}

export function AttachmentVisibilityModal({
  opened,
  onClose,
  attachmentId,
  initialItem,
  onUpdated,
}: {
  opened: boolean;
  onClose: () => void;
  attachmentId: string;
  initialItem?: TGalleryItem | null;
  onUpdated?: (item: TGalleryItem) => void;
}) {
  const { t } = useTranslation();
  const editor = useAttachmentVisibilityEditor(opened, attachmentId, initialItem);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t("gallery-visibility")}
      centered
    >
      <Stack gap="sm">
        <VisibilityFields editor={editor} />
        <Group justify="flex-end" gap="sm">
          <Button variant="default" onClick={onClose} disabled={editor.saving}>
            {t("cancel")}
          </Button>
          <Button
            loading={editor.saving}
            disabled={editor.loading || !editor.canManage}
            onClick={() => {
              void editor.save((item) => {
                onUpdated?.(item);
                onClose();
              });
            }}
          >
            {t("save")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function AttachmentDetailsModal({
  opened,
  onClose,
  attachmentId,
  fallbackName,
  fallbackUrl,
  initialItem,
  onUpdated,
}: {
  opened: boolean;
  onClose: () => void;
  attachmentId?: string;
  fallbackName: string;
  fallbackUrl?: string;
  initialItem?: TGalleryItem | null;
  onUpdated?: (item: TGalleryItem) => void;
}) {
  const { t, i18n } = useTranslation();
  const editor = useAttachmentVisibilityEditor(
    opened,
    attachmentId,
    initialItem
  );
  const name = editor.item?.name || fallbackName;
  const url = editor.item?.url || fallbackUrl || "";
  const created = formatCreatedAt(editor.item?.created_at, i18n.language);
  const typeLabel = getDocumentFileMeta(
    name,
    editor.item?.content_type || ""
  ).label;
  const currentVisibility = editor.item?.visibility || initialItem?.visibility;
  const showAccess = Boolean(attachmentId);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t("attachment-details")}
      centered
    >
      <Stack gap="md">
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <DocumentFileIcon
            name={name}
            contentType={editor.item?.content_type}
            size={28}
          />
          <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
            <Text size="sm" fw={600} lineClamp={3}>
              {name}
            </Text>
            <Text size="xs" c="dimmed">
              {t("attachment-type")}: {typeLabel}
              {created ? ` · ${created}` : ""}
              {currentVisibility
                ? ` · ${t(visibilityLabelKey(currentVisibility))}`
                : ""}
            </Text>
          </Stack>
        </Group>
        {url ? (
          <Button
            component="a"
            href={url}
            download={name}
            target="_blank"
            rel="noopener noreferrer"
            variant="default"
            leftSection={<IconDownload size={16} />}
          >
            {t("download")}
          </Button>
        ) : null}
        {showAccess && !editor.loadError ? (
          <>
            <Divider label={t("attachment-access")} labelPosition="left" />
            <VisibilityFields editor={editor} />
            <Group justify="flex-end" gap="sm">
              <Button variant="default" onClick={onClose} disabled={editor.saving}>
                {t("cancel")}
              </Button>
              <Button
                loading={editor.saving}
                disabled={editor.loading || !editor.canManage}
                onClick={() => {
                  void editor.save((item) => {
                    onUpdated?.(item);
                    onClose();
                  });
                }}
              >
                {t("save")}
              </Button>
            </Group>
          </>
        ) : (
          <Stack gap="sm">
            {showAccess && editor.loadError ? (
              <Text size="sm" c="dimmed">
                {t("attachment-access-unavailable")}
              </Text>
            ) : null}
            <Group justify="flex-end">
              <Button variant="default" onClick={onClose}>
                {t("cancel")}
              </Button>
            </Group>
          </Stack>
        )}
      </Stack>
    </Modal>
  );
}
