import React, { useEffect, useState } from "react";
import {
  Modal,
  TextInput,
  Textarea,
  Button,
  Badge,
  Group,
  Stack,
  Title,
  Text,
  Loader,
  ActionIcon,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { TConversation, TTag } from "../../types";
import { updateConversation, getTags, getTag } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useStore } from "../../modules/store";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { IconDeviceFloppy, IconPlus, IconX } from "@tabler/icons-react";

const MAX_CONVERSATION_TAGS = 3;

export const ConversationModal = ({
  conversation,
  readOnly = false,
  showTitleTrigger = true,
  editorOpened: editorOpenedProp,
  onEditorOpen,
  onEditorClose,
}: {
  conversation: TConversation;
  readOnly?: boolean;
  /** When false, only editor modals render (e.g. mobile menu opens editor). */
  showTitleTrigger?: boolean;
  editorOpened?: boolean;
  onEditorOpen?: () => void;
  onEditorClose?: () => void;
}) => {
  const [internalOpened, { open: internalOpen, close: internalClose }] =
    useDisclosure(false);
  const isEditorControlled = editorOpenedProp !== undefined;
  const opened = isEditorControlled ? editorOpenedProp : internalOpened;
  const openEditor = () => {
    if (isEditorControlled) onEditorOpen?.();
    else internalOpen();
  };
  const closeEditor = () => {
    if (isEditorControlled) onEditorClose?.();
    else internalClose();
  };
  const [addTagsOpened, { open: openAddTags, close: closeAddTags }] =
    useDisclosure(false);
  const [title, setTitle] = useState(conversation.title);
  const [summaryText, setSummaryText] = useState(conversation.summary ?? "");
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [resolvedTags, setResolvedTags] = useState<TTag[]>([]);
  const [loadingResolvedTags, setLoadingResolvedTags] = useState(false);
  const [orgTagsForPicker, setOrgTagsForPicker] = useState<TTag[]>([]);
  const [loadingPickerTags, setLoadingPickerTags] = useState(false);
  const [pickerChosenIds, setPickerChosenIds] = useState<number[]>([]);

  const { t } = useTranslation();
  const canEditConversationMeta =
    useIsFeatureEnabled("can-edit-conversation-data") === true;
  /** Channel threads (widget/WhatsApp) use readOnly for the composer only; metadata edits use the flag. */
  const canMutateTitleAndTags = canEditConversationMeta;
  const canOpenModal = readOnly || canEditConversationMeta;

  const { socket } = useStore((s) => ({
    socket: s.socket,
  }));

  useEffect(() => {
    socket.on("title_updated", (data) => {
      if (data.message.conversation_id === conversation.id) {
        setTitle(data.message.title);
      }
    });
    return () => {
      socket.off("title_updated");
    };
  }, [socket, conversation]);

  useEffect(() => {
    setTitle(conversation.title);
    setSummaryText(conversation.summary ?? "");
    setSelectedTagIds(
      Array.isArray(conversation.tags)
        ? conversation.tags.map((t) => Number(t)).filter((n) => !isNaN(n))
        : []
    );
  }, [conversation]);

  useEffect(() => {
    if (!opened) return;
    let cancelled = false;
    (async () => {
      setLoadingResolvedTags(true);
      try {
        const ids = [...selectedTagIds];
        if (ids.length === 0) {
          if (!cancelled) setResolvedTags([]);
        } else {
          const results = await Promise.all(
            ids.map((id) => getTag(id).catch(() => null))
          );
          if (cancelled) return;
          const byId = new Map(
            (results.filter(Boolean) as TTag[]).map((tag) => [tag.id, tag])
          );
          const ordered: TTag[] = [];
          for (const id of ids.slice(0, MAX_CONVERSATION_TAGS)) {
            const tag = byId.get(id);
            if (tag) ordered.push(tag);
          }
          setResolvedTags(ordered);
        }
      } finally {
        if (!cancelled) setLoadingResolvedTags(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [opened, selectedTagIds]);

  useEffect(() => {
    if (!addTagsOpened) return;
    let cancelled = false;
    setLoadingPickerTags(true);
    setPickerChosenIds([]);
    (async () => {
      try {
        const tags = await getTags();
        if (!cancelled) setOrgTagsForPicker(Array.isArray(tags) ? tags : []);
      } catch {
        if (!cancelled) setOrgTagsForPicker([]);
      } finally {
        if (!cancelled) setLoadingPickerTags(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [addTagsOpened]);

  const handleCloseMain = () => {
    closeAddTags();
    closeEditor();
  };

  const removeTag = (tagId: number) => {
    setSelectedTagIds((prev) => prev.filter((id) => id !== tagId));
  };

  const slotsLeft = MAX_CONVERSATION_TAGS - selectedTagIds.length;

  const togglePickerTag = (tagId: number) => {
    setPickerChosenIds((prev) => {
      if (prev.includes(tagId)) {
        return prev.filter((id) => id !== tagId);
      }
      if (prev.length >= slotsLeft) return prev;
      return [...prev, tagId];
    });
  };

  const applyPickerSelection = () => {
    const newIds = pickerChosenIds.filter((id) => !selectedTagIds.includes(id));
    const merged = [...selectedTagIds, ...newIds].slice(0, MAX_CONVERSATION_TAGS);
    setSelectedTagIds(merged);
    closeAddTags();
  };

  const handleSave = async () => {
    await updateConversation(conversation.id, {
      title: title,
      tags: selectedTagIds,
      summary: summaryText.trim() || null,
    });
    toast.success(t("conversation-updated"));
    handleCloseMain();
  };

  const availableToPick = orgTagsForPicker.filter(
    (tag) => tag.enabled && !selectedTagIds.includes(tag.id)
  );

  return (
    <>
      {showTitleTrigger && (
        <p
          onClick={canOpenModal ? openEditor : undefined}
          className={`cutted-text${canOpenModal ? " pressable" : ""}`}
          style={!canOpenModal ? { cursor: "default" } : undefined}
        >
          {title ? `${title.slice(0, 25)}...` : t("conversation-without-title")}
        </p>
      )}

      <Modal
        opened={opened}
        onClose={handleCloseMain}
        title={<Title order={4}>{t("conversation-editor")}</Title>}
        centered
        size="lg"
        overlayProps={{
          backgroundOpacity: 0.55,
          blur: 3,
        }}
      >
        <Stack gap="md">
          <TextInput
            label={t("title")}
            value={title ?? ""}
            onChange={(e) => setTitle(e.currentTarget.value)}
            readOnly={!canMutateTitleAndTags}
          />

          <Textarea
            label={t("conversation-summary")}
            description={t("conversation-summary-hint")}
            placeholder={t("conversation-summary-empty")}
            value={summaryText}
            onChange={(e) => setSummaryText(e.currentTarget.value)}
            readOnly={!canMutateTitleAndTags}
            minRows={3}
            maxRows={12}
            autosize
          />

          <div>
            <Text size="sm" fw={500} mb={4}>
              {t("conversation-tags-current")}
            </Text>

            {loadingResolvedTags ? (
              <Group justify="center" py="sm">
                <Loader size="sm" />
              </Group>
            ) : selectedTagIds.length === 0 ? (
              <Text size="xs" c="dimmed">
                {t("conversation-no-tags-yet")}
              </Text>
            ) : (
              <Group gap="xs" wrap="wrap" align="center">
                {selectedTagIds.map((id) => {
                  const meta = resolvedTags.find((x) => x.id === id);
                  const label = meta?.title ?? `${t("tag-unavailable")} (${id})`;
                  const color = meta?.color || "violet";
                  return (
                    <Group key={id} gap={4} wrap="nowrap">
                      <Badge variant="filled" color={color}>
                        {label}
                      </Badge>
                      {canMutateTitleAndTags && (
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          size="sm"
                          aria-label="Remove tag"
                          onClick={() => removeTag(id)}
                        >
                          <IconX size={14} />
                        </ActionIcon>
                      )}
                    </Group>
                  );
                })}
              </Group>
            )}

            {canMutateTitleAndTags && selectedTagIds.length < MAX_CONVERSATION_TAGS && (
              <Button
                variant="light"
                size="xs"
                mt="xs"
                leftSection={<IconPlus size={16} />}
                onClick={openAddTags}
                title={t("max-tags-on-conversation")}
              >
                {t("add-tags")}
              </Button>
            )}
          </div>

          {canMutateTitleAndTags && (
            <Button
              onClick={handleSave}
              leftSection={<IconDeviceFloppy size={18} />}
              fullWidth
              variant="light"
            >
              {t("save")}
            </Button>
          )}
        </Stack>
      </Modal>

      <Modal
        opened={addTagsOpened}
        onClose={closeAddTags}
        title={<Title order={5}>{t("add-tags-modal-title")}</Title>}
        centered
        size="md"
        overlayProps={{
          backgroundOpacity: 0.45,
          blur: 2,
        }}
      >
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {t("add-tags-modal-hint")}
          </Text>
          {slotsLeft <= 0 ? (
            <Text size="sm">{t("max-tags-on-conversation")}</Text>
          ) : loadingPickerTags ? (
            <Group justify="center" py="md">
              <Loader size="sm" />
            </Group>
          ) : availableToPick.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t("no-additional-tags-available")}
            </Text>
          ) : (
            <>
              <Group gap="xs" wrap="wrap">
                {availableToPick.map((tag) => {
                  const chosen = pickerChosenIds.includes(tag.id);
                  return (
                    <Badge
                      key={tag.id}
                      variant={chosen ? "filled" : "outline"}
                      color={tag.color || "violet"}
                      style={{ cursor: "pointer" }}
                      onClick={() => togglePickerTag(tag.id)}
                    >
                      {tag.title}
                    </Badge>
                  );
                })}
              </Group>
              <Button
                onClick={applyPickerSelection}
                disabled={pickerChosenIds.length === 0}
                fullWidth
                variant="light"
              >
                {t("add-tags-apply")}
              </Button>
            </>
          )}
        </Stack>
      </Modal>
    </>
  );
};
