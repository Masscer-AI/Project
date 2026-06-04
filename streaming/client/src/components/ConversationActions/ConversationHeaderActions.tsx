import React from "react";
import {
  Modal,
  Button,
  ActionIcon,
  Group,
  Text,
  Tooltip,
  Menu,
} from "@mantine/core";
import { useDisclosure, useMediaQuery } from "@mantine/hooks";
import {
  IconShare,
  IconBarbell,
  IconTrash,
  IconDotsVertical,
  IconPencil,
} from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { deleteConversation } from "../../modules/apiCalls";
import { TConversation } from "../../types";
import { ConversationModal } from "../ConversationModal/ConversationModal";
import { ShareConversationModal } from "./ShareConversationModal";
import { TrainOnConversationModal } from "./TrainOnConversationModal";

export const ConversationHeaderActions = ({
  conversation,
  readOnly = false,
  showActions = true,
  onDeleted,
}: {
  conversation: TConversation;
  /** When true, conversation editor fields are read-only (rare; metadata uses can-edit flag). */
  readOnly?: boolean;
  /** When false, hides share/train/delete/edit menu (e.g. another user's personal chat). */
  showActions?: boolean;
  onDeleted?: () => void;
}) => {
  const { t } = useTranslation();
  const isTrainAgentsEnabled = useIsFeatureEnabled("train-agents");
  const canEditConversationData =
    useIsFeatureEnabled("can-edit-conversation-data") === true;
  const isCompactActions = useMediaQuery("(max-width: 48em)");

  const [shareOpened, { open: openShare, close: closeShare }] =
    useDisclosure(false);
  const [trainOpened, { open: openTrain, close: closeTrain }] =
    useDisclosure(false);
  const [deleteOpened, { open: openDelete, close: closeDelete }] =
    useDisclosure(false);
  const [editorOpened, { open: openEditor, close: closeEditor }] =
    useDisclosure(false);

  const canOpenEditor = readOnly || canEditConversationData;

  const handleDelete = async () => {
    await deleteConversation(conversation.id);
    closeDelete();
    onDeleted?.();
  };

  const shareControl = (
    <Tooltip label={t("share")} disabled={isCompactActions}>
      <ActionIcon
        variant="subtle"
        color="gray"
        size="sm"
        aria-label={t("share")}
        onClick={openShare}
      >
        <IconShare size={18} />
      </ActionIcon>
    </Tooltip>
  );

  const trainControl = isTrainAgentsEnabled ? (
    <Tooltip label={t("train")} disabled={isCompactActions}>
      <ActionIcon
        variant="subtle"
        color="gray"
        size="sm"
        aria-label={t("train")}
        onClick={openTrain}
      >
        <IconBarbell size={18} />
      </ActionIcon>
    </Tooltip>
  ) : null;

  const deleteControl = canEditConversationData ? (
    <Tooltip label={t("delete")} disabled={isCompactActions}>
      <ActionIcon
        variant="subtle"
        color="red"
        size="sm"
        aria-label={t("delete")}
        onClick={openDelete}
      >
        <IconTrash size={18} />
      </ActionIcon>
    </Tooltip>
  ) : null;

  return (
    <>
      <Group
        gap="xs"
        justify="flex-end"
        wrap="nowrap"
        style={{ minWidth: 0 }}
      >
        <div
          style={{
            minWidth: 0,
            flex: isCompactActions ? "0 0 auto" : "1 1 auto",
            overflow: "hidden",
          }}
        >
          <ConversationModal
            conversation={conversation}
            readOnly={readOnly}
            showTitleTrigger={!isCompactActions}
            editorOpened={isCompactActions ? editorOpened : undefined}
            onEditorOpen={isCompactActions ? openEditor : undefined}
            onEditorClose={isCompactActions ? closeEditor : undefined}
          />
        </div>
        {showActions &&
          (isCompactActions ? (
            <Menu position="bottom-end" withArrow shadow="md">
              <Menu.Target>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  size="sm"
                  aria-label={t("conversation-options")}
                >
                  <IconDotsVertical size={18} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                {canOpenEditor && (
                  <Menu.Item
                    leftSection={<IconPencil size={16} />}
                    onClick={openEditor}
                  >
                    {t("edit")}
                  </Menu.Item>
                )}
                <Menu.Item
                  leftSection={<IconShare size={16} />}
                  onClick={openShare}
                >
                  {t("share")}
                </Menu.Item>
                {isTrainAgentsEnabled && (
                  <Menu.Item
                    leftSection={<IconBarbell size={16} />}
                    onClick={openTrain}
                  >
                    {t("train")}
                  </Menu.Item>
                )}
                {canEditConversationData && (
                  <Menu.Item
                    color="red"
                    leftSection={<IconTrash size={16} />}
                    onClick={openDelete}
                  >
                    {t("delete")}
                  </Menu.Item>
                )}
              </Menu.Dropdown>
            </Menu>
          ) : (
            <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
              {shareControl}
              {trainControl}
              {deleteControl}
            </Group>
          ))}
      </Group>

      <ShareConversationModal
        opened={shareOpened}
        onClose={closeShare}
        conversationId={conversation.id}
      />
      <TrainOnConversationModal
        opened={trainOpened}
        onClose={closeTrain}
        conversation={conversation}
      />
      {canEditConversationData && (
        <Modal
          opened={deleteOpened}
          onClose={closeDelete}
          title={t("delete-conversation")}
          size="sm"
          centered
        >
          <Text size="sm" mb="md">
            {t("sure")}?
          </Text>
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={closeDelete}>
              {t("cancel")}
            </Button>
            <Button color="red" onClick={handleDelete}>
              {t("delete")}
            </Button>
          </Group>
        </Modal>
      )}
    </>
  );
};
