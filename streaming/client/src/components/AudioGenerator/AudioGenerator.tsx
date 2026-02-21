import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  generateAudio,
  getUserVoices,
  updateUserVoices,
  TVoice,
} from "../../modules/apiCalls";
import {
  Modal,
  Button,
  Textarea,
  NativeSelect,
  Stack,
  Group,
  TextInput,
} from "@mantine/core";
import { IconVolume, IconPlus } from "@tabler/icons-react";

const removeDuplicateVoices = (voices: TVoice[]) => {
  const seen = new Set();
  return voices.filter((v) => {
    const key = `${v.provider}-${v.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export const AudioGenerator = ({
  messageId,
  text,
  opened,
  onClose,
}: {
  messageId: string;
  text: string;
  opened?: boolean;
  onClose?: () => void;
}) => {
  const isExternallyControlled = opened !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const modalOpened = isExternallyControlled ? opened : internalOpen;

  const [audioText, setAudioText] = useState(text);
  const [voice, setVoice] = useState<TVoice | null>(null);
  const [voiceList, setVoiceList] = useState<TVoice[]>([]);
  const { t } = useTranslation();

  useEffect(() => {
    setAudioText(text);
  }, [text]);

  useEffect(() => {
    const fetchVoices = async () => {
      const fetchedVoices = await getUserVoices();
      const merged = removeDuplicateVoices(fetchedVoices);
      setVoiceList(merged);
      if (merged.length > 0 && !voice) setVoice(merged[0]);
    };
    fetchVoices();
  }, []);

  const handleClose = () => {
    if (isExternallyControlled && onClose) {
      onClose();
    } else {
      setInternalOpen(false);
    }
  };

  const addElevenVoice = (id: string, name: string) => {
    setVoiceList((prev) => {
      const newVoices = removeDuplicateVoices([
        ...prev,
        { provider: "elevenlabs", id, name },
      ]);
      updateUserVoices(newVoices);
      return newVoices;
    });
  };

  const generateSpeech = async () => {
    if (!voice) return;
    toast.success(t("generating-speech"));
    await generateAudio({
      text: audioText,
      voice,
      message_id: messageId,
    });
    handleClose();
  };

  const selectedVoiceValue = voice?.id ?? "";

  return (
    <>
      {!isExternallyControlled && (
        <Button
          variant="default"
          size="xs"
          leftSection={<IconVolume size={16} />}
          onClick={() => setInternalOpen(true)}
          fullWidth
        >
          {t("generate-speech")}
        </Button>
      )}
      <Modal
        opened={!!modalOpened}
        onClose={handleClose}
        title={t("generate-speech")}
        centered
        size="md"
      >
        <Stack gap="md">
          <Textarea
            label={t("enter-text-to-generate-audio")}
            value={audioText}
            onChange={(e) => setAudioText(e.currentTarget.value)}
            autosize
            minRows={3}
            maxRows={10}
          />
          <Group gap="sm" align="end">
            <NativeSelect
              label="Voice"
              value={selectedVoiceValue}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setVoice(voiceList.find((v) => v.id === val)!);
              }}
              data={voiceList.map((v) => ({
                value: v.id,
                label: `${v.name} (${v.provider})`,
              }))}
              style={{ flex: 1 }}
            />
            <AddElevenVoice addElevenVoice={addElevenVoice} />
          </Group>
          <Button
            leftSection={<IconVolume size={16} />}
            onClick={generateSpeech}
          >
            {t("generate")}
          </Button>
        </Stack>
      </Modal>
    </>
  );
};

const AddElevenVoice = ({
  addElevenVoice,
}: {
  addElevenVoice: (id: string, name: string) => void;
}) => {
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.target as HTMLFormElement);
    const id = formData.get("voice_id") as string;
    const name = formData.get("voice_name") as string;

    if (!id || !name) {
      toast.error(t("please-enter-voice-id-and-name"));
      return;
    }
    addElevenVoice(id, name);
    setOpen(false);
  };

  return (
    <>
      <Button
        variant="default"
        size="xs"
        leftSection={<IconPlus size={16} />}
        onClick={() => setOpen(true)}
      >
        {t("add-elevenlabs-voice")}
      </Button>
      <Modal
        opened={open}
        onClose={() => setOpen(false)}
        title={t("add-elevenlabs-voice")}
        centered
      >
        <form onSubmit={handleSubmit}>
          <Stack gap="md">
            <TextInput
              name="voice_id"
              label="Voice ID"
              placeholder={t("enter-voice-id")}
              required
            />
            <TextInput
              name="voice_name"
              label="Voice Name"
              placeholder={t("enter-voice-name")}
              required
            />
            <Button
              type="submit"
              leftSection={<IconPlus size={16} />}
            >
              {t("add-elevenlabs-voice")}
            </Button>
          </Stack>
        </form>
      </Modal>
    </>
  );
};
