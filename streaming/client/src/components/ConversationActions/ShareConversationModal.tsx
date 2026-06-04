import React, { useState } from "react";
import {
  Modal,
  Button,
  TextInput,
  Group,
  Stack,
  Text,
} from "@mantine/core";
import { IconShare, IconCopy, IconExternalLink } from "@tabler/icons-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { shareConversation } from "../../modules/apiCalls";
import { QRCodeDisplay } from "../QRGenerator/QRGenerator";

export const ShareConversationModal = ({
  opened,
  onClose,
  conversationId,
}: {
  opened: boolean;
  onClose: () => void;
  conversationId: string;
}) => {
  const [validUntil, setValidUntil] = useState<Date | null>(null);
  const { t } = useTranslation();
  const [sharedId, setSharedId] = useState("");

  const share = async () => {
    const tid = toast.loading(t("sharing-conversation"));
    try {
      const res = await shareConversation(conversationId, validUntil);
      toast.dismiss(tid);
      setSharedId(res.id);
    } catch (e) {
      console.error("Failed to share conversation", e);
      toast.dismiss(tid);
      toast.error(t("failed-to-share-conversation"));
    }
  };

  const formatDateToLocalString = (date: Date) => {
    return date.toISOString().slice(0, 16);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success(t("copied-to-clipboard"));
  };

  const generateShareLink = () => {
    return `${window.location.origin}/s?id=${sharedId}`;
  };

  const openLink = () => {
    window.open(generateShareLink(), "_blank");
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      onExitTransitionEnd={() => setSharedId("")}
      title={t("share-conversation")}
      centered
    >
      <Stack gap="md">
        {!sharedId ? (
          <>
            <Text>{t("share-conversation-description")}</Text>
            <TextInput
              type="datetime-local"
              defaultValue={
                validUntil ? formatDateToLocalString(validUntil) : ""
              }
              onChange={(e) => setValidUntil(new Date(e.currentTarget.value))}
            />
            <Button
              leftSection={<IconShare size={18} />}
              onClick={share}
              fullWidth
            >
              {t("share-now")}
            </Button>
          </>
        ) : (
          <>
            <Text ta="center" p="md" className="bg-green-500/20 rounded-lg">
              {t("conversation-shared-message")}
            </Text>
            <div className="qr-display">
              <QRCodeDisplay size={256} url={generateShareLink()} />
            </div>
            <TextInput value={generateShareLink()} readOnly variant="filled" />
            <Group gap="xs" grow>
              <Button
                variant="default"
                leftSection={<IconCopy size={18} />}
                onClick={() => copyToClipboard(generateShareLink())}
              >
                {t("copy")}
              </Button>
              <Button
                variant="default"
                leftSection={<IconExternalLink size={18} />}
                onClick={openLink}
              >
                {t("open-link")}
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Modal>
  );
};
