import React, { useEffect, useState } from "react";
import { Modal, TextInput, Button, Badge, Group, Stack, Title, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { TConversation } from "../../types";
import { updateConversation } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useStore } from "../../modules/store";
import { IconDeviceFloppy } from "@tabler/icons-react";

export const ConversationModal = ({
  conversation,
}: {
  conversation: TConversation;
}) => {
  const [opened, { open, close }] = useDisclosure(false);
  const [title, setTitle] = useState(conversation.title);
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");

  const { t } = useTranslation();

  const { userTags, socket } = useStore((s) => ({
    userTags: s.userTags,
    socket: s.socket,
  }));

  const onTagSubmit = () => {
    const newTags = tagInput
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag !== "" && !tags.includes(tag));

    if (newTags.length > 0) {
      setTags((prev) => [...prev, ...newTags]);
      setTagInput("");
    }
  };

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
    setTags(conversation.tags?.map(String) || []);
  }, [conversation]);

  const handleSave = async () => {
    await updateConversation(conversation.id, {
      title: title,
      tags: tags,
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
          />

          <div>
            <Text size="sm" fw={500} mb={4}>
              {t("tags")}
            </Text>

            {tags.length > 0 && (
              <Group gap="xs" mb="sm">
                {tags.map((tag) => (
                  <Badge
                    key={tag}
                    variant="light"
                    rightSection={
                      <span
                        style={{ cursor: "pointer", marginLeft: 4 }}
                        onClick={() => setTags(tags.filter((t) => t !== tag))}
                      >
                        &times;
                      </span>
                    }
                  >
                    {tag}
                  </Badge>
                ))}
              </Group>
            )}

            <TextInput
              value={tagInput}
              onChange={(e) => setTagInput(e.currentTarget.value)}
              onBlur={onTagSubmit}
              onKeyDown={(e) => {
                if (e.key === "Enter") onTagSubmit();
              }}
              placeholder={t("tag-examples")}
            />
          </div>

          {userTags.filter((tag) => !tags.includes(tag)).length > 0 && (
            <div>
              <Text size="xs" c="dimmed" mb={4}>
                {t("previously-used-tags")}
              </Text>
              <Group gap="xs">
                {userTags
                  .filter((tag) => !tags.includes(tag))
                  .map((tag) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      style={{ cursor: "pointer" }}
                      onClick={() => setTags([...tags, tag])}
                    >
                      {tag}
                    </Badge>
                  ))}
              </Group>
            </div>
          )}

          <Button
            onClick={handleSave}
            leftSection={<IconDeviceFloppy size={18} />}
            fullWidth
            variant="light"
          >
            {t("save")}
          </Button>
        </Stack>
      </Modal>
    </>
  );
};
