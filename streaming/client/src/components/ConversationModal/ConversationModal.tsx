import React, { useEffect, useState } from "react";
import {
  Modal,
  TextInput,
  Button,
  Badge,
  Group,
  Stack,
  Title,
  Text,
  Loader,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { TConversation, TTag } from "../../types";
import { updateConversation, getTags } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useStore } from "../../modules/store";
import { IconDeviceFloppy } from "@tabler/icons-react";

export const ConversationModal = ({
  conversation,
  readOnly = false,
}: {
  conversation: TConversation;
  readOnly?: boolean;
}) => {
  const [opened, { open, close }] = useDisclosure(false);
  const [title, setTitle] = useState(conversation.title);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [orgTags, setOrgTags] = useState<TTag[]>([]);
  const [loadingTags, setLoadingTags] = useState(false);

  const { t } = useTranslation();

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
    // conversation.tags is number[] (Tag IDs) from the backend
    setSelectedTagIds(
      Array.isArray(conversation.tags)
        ? conversation.tags.map((t) => Number(t)).filter((n) => !isNaN(n))
        : []
    );
  }, [conversation]);

  // Fetch organization tags when modal opens
  useEffect(() => {
    if (!opened) return;
    let cancelled = false;
    const loadOrgTags = async () => {
      setLoadingTags(true);
      try {
        const tags = await getTags();
        if (!cancelled) setOrgTags(tags);
      } catch {
        // User may not have tags-management permission — that's ok
        if (!cancelled) setOrgTags([]);
      } finally {
        if (!cancelled) setLoadingTags(false);
      }
    };
    loadOrgTags();
    return () => {
      cancelled = true;
    };
  }, [opened]);

  const toggleTag = (tagId: number) => {
    setSelectedTagIds((prev) =>
      prev.includes(tagId)
        ? prev.filter((id) => id !== tagId)
        : [...prev, tagId]
    );
  };

  const handleSave = async () => {
    await updateConversation(conversation.id, {
      title: title,
      tags: selectedTagIds,
    });
    toast.success(t("conversation-updated"));
    close();
  };

  return (
    <>
      <p onClick={open} className="cutted-text pressable">
        {title ? `${title.slice(0, 25)}...` : t("conversation-without-title")}
      </p>

      <Modal
        opened={opened}
        onClose={close}
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
            readOnly={readOnly}
          />

          <div>
            <Text size="sm" fw={500} mb={4}>
              {t("tags")}
            </Text>

            {loadingTags ? (
              <Group justify="center" py="sm">
                <Loader size="sm" />
              </Group>
            ) : orgTags.length > 0 ? (
              <Group gap="xs" wrap="wrap">
                {orgTags
                  .filter((tag) => tag.enabled)
                  .map((tag) => {
                    const isSelected = selectedTagIds.includes(tag.id);
                    return (
                      <Badge
                        key={tag.id}
                        variant={isSelected ? "filled" : "outline"}
                        color={tag.color || "violet"}
                        style={{ cursor: readOnly ? "default" : "pointer" }}
                        onClick={readOnly ? undefined : () => toggleTag(tag.id)}
                      >
                        {tag.title}
                      </Badge>
                    );
                  })}
              </Group>
            ) : (
              <Text size="xs" c="dimmed">
                {t("no-tags-available")}
              </Text>
            )}
          </div>

          {!readOnly && (
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
    </>
  );
};
