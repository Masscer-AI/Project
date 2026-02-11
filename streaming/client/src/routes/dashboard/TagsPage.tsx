import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import {
  getTags,
  createTag,
  updateTag,
  deleteTag,
  getUser,
} from "../../modules/apiCalls";
import { TTag } from "../../types";
import { TUserData } from "../../types/chatTypes";
import { useTranslation } from "react-i18next";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { DashboardLayout } from "./DashboardLayout";
import {
  Badge,
  Button,
  Card,
  Checkbox,
  ColorInput,
  ColorSwatch,
  Divider,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";

export default function TagsPage() {
  const { startup, setUser } = useStore((state) => ({
    startup: state.startup,
    setUser: state.setUser,
  }));
  const { t } = useTranslation();
  const canManageTags = useIsFeatureEnabled("tags-management");
  const [tags, setTags] = useState<TTag[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingTag, setEditingTag] = useState<TTag | null>(null);
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    color: "#4a9eff",
    enabled: true,
  });

  useEffect(() => {
    const loadUser = async () => {
      try {
        const user = (await getUser()) as TUserData;
        setUser(user);
      } catch (error) {
        console.error("Error loading user:", error);
      }
    };
    loadUser();
    startup();
  }, [startup, setUser]);

  useEffect(() => {
    if (canManageTags === true) {
      loadTags();
    }
  }, [canManageTags]);

  const loadTags = async () => {
    try {
      setIsLoading(true);
      const data = await getTags();
      setTags(data);
    } catch (error) {
      console.error("Error loading tags:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingTag(null);
    setFormData({
      title: "",
      description: "",
      color: "#4a9eff",
      enabled: true,
    });
    setShowForm(true);
  };

  const handleEdit = (tag: TTag) => {
    setEditingTag(tag);
    setFormData({
      title: tag.title,
      description: tag.description || "",
      color: tag.color || "#4a9eff",
      enabled: tag.enabled,
    });
    setShowForm(true);
  };

  const handleDelete = async (tagId: number) => {
    if (
      !window.confirm(
        t("confirm-delete-tag") || "Are you sure you want to delete this tag?"
      )
    ) {
      return;
    }
    try {
      await deleteTag(tagId);
      loadTags();
    } catch (error) {
      console.error("Error deleting tag:", error);
      alert(t("error-deleting-tag") || "Error deleting tag");
    }
  };

  const handleSubmit = async () => {
    try {
      if (editingTag) {
        await updateTag(editingTag.id, formData);
      } else {
        await createTag(formData);
      }
      setShowForm(false);
      setEditingTag(null);
      loadTags();
    } catch (error: any) {
      console.error("Error saving tag:", error);
      alert(
        error.response?.data?.message ||
          t("error-saving-tag") ||
          "Error saving tag"
      );
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingTag(null);
  };

  const PRESET_COLORS = [
    "#4a9eff",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#ec4899",
    "#06b6d4",
    "#84cc16",
  ];

  if (canManageTags === false) {
    return null;
  }

  return (
    <DashboardLayout>
      <Stack gap="lg">
        <Title order={2} ta="center">
          {t("tags") || "Tags"}
        </Title>

        <Group justify="center">
          <Button
            variant="default"
            leftSection={<IconPlus size={16} />}
            onClick={handleCreate}
          >
            {t("create-tag") || "+ New Tag"}
          </Button>
        </Group>

        {isLoading ? (
          <Group justify="center" py="xl">
            <Loader />
          </Group>
        ) : tags.length === 0 ? (
          <Text ta="center" c="dimmed" py="xl" size="lg">
            {t("no-tags-found") ||
              "No tags found. Create your first one!"}
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }} spacing="md">
            {tags.map((tag) => (
              <TagCard
                key={tag.id}
                tag={tag}
                onEdit={handleEdit}
                onDelete={handleDelete}
                t={t}
              />
            ))}
          </SimpleGrid>
        )}
      </Stack>

      {/* Create/Edit Modal */}
      <Modal
        opened={showForm}
        onClose={handleCancel}
        title={
          editingTag
            ? t("edit-tag") || "Edit Tag"
            : t("create-tag") || "Create Tag"
        }
        size="md"
        centered
      >
        <Stack gap="md">
          <TextInput
            label={t("title") || "Title"}
            value={formData.title}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setFormData((prev) => ({ ...prev, title: val }));
            }}
            required
            maxLength={50}
            placeholder={
              t("tag-title-placeholder") ||
              "Tag title (max 50 characters)"
            }
          />
          <Textarea
            label={t("description") || "Description"}
            value={formData.description}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setFormData((prev) => ({ ...prev, description: val }));
            }}
            autosize
            minRows={3}
            placeholder={
              t("tag-description-placeholder") ||
              "Tag description (optional)"
            }
          />
          <ColorInput
            label={t("color") || "Color"}
            value={formData.color}
            onChange={(val) =>
              setFormData((prev) => ({ ...prev, color: val }))
            }
            swatches={PRESET_COLORS}
          />
          <Checkbox
            label={t("enabled") || "Enabled"}
            checked={formData.enabled}
            onChange={(e) => {
              const checked = e.currentTarget.checked;
              setFormData((prev) => ({ ...prev, enabled: checked }));
            }}
          />
          <Divider />
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={handleCancel}>
              {t("cancel") || "Cancel"}
            </Button>
            <Button onClick={handleSubmit}>
              {editingTag
                ? t("update") || "Update"
                : t("create") || "Create"}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </DashboardLayout>
  );
}

function TagCard({
  tag,
  onEdit,
  onDelete,
  t,
}: {
  tag: TTag;
  onEdit: (tag: TTag) => void;
  onDelete: (tagId: number) => void;
  t: any;
}) {
  return (
    <Card withBorder padding="lg" radius="md">
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Group gap="sm">
            <ColorSwatch color={tag.color || "#4a9eff"} size={16} />
            <Text fw={600}>{tag.title}</Text>
          </Group>
          <Badge color={tag.enabled ? "green" : "red"} size="sm">
            {tag.enabled
              ? t("enabled") || "Enabled"
              : t("disabled") || "Disabled"}
          </Badge>
        </Group>

        {tag.description && (
          <Text size="sm" c="dimmed">
            {tag.description}
          </Text>
        )}

        <Divider />

        <Group gap="xs">
          <Button variant="default" size="xs" onClick={() => onEdit(tag)}>
            {t("edit") || "Edit"}
          </Button>
          <Button
            variant="default"
            size="xs"
            color="red"
            onClick={() => onDelete(tag.id)}
          >
            {t("delete") || "Delete"}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}
