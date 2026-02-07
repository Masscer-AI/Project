import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import { SvgButton } from "../SvgButton/SvgButton";
import { Icon } from "../Icon/Icon";
import { Textarea } from "../SimpleForm/Textarea";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  generateAudio,
  getUserVoices,
  updateUserVoices,
  TVoice,
} from "../../modules/apiCalls";

const voices = [
  {
    provider: "openai",
    id: "alloy",
    name: "Alloy",
  },
  {
    provider: "openai",
    id: "echo",
    name: "Echo",
  },
  {
    provider: "openai",
    id: "fable",
    name: "Fable",
  },
  {
    provider: "openai",
    id: "onyx",
    name: "Onyx",
  },
  {
    provider: "openai",
    id: "nova",
    name: "Nova",
  },
  {
    provider: "openai",
    id: "shimmer",
    name: "Shimmer",
  },
];

const removeOpenaiVoices = (voices: TVoice[]) => {
  return voices.filter((v) => v.provider !== "openai");
};

const removeDuplicateVoices = (voices: TVoice[]) => {
  const seen = new Set();
  return voices.filter((v) => {
    const key = `${v.provider}-${v.id}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
};

const fixVoices = (voices: TVoice[]) => {
  return removeDuplicateVoices(removeOpenaiVoices(voices));
};

export const AudioGenerator = ({
  messageId,

  text,
}: {
  messageId: string;
  text: string;
}) => {
  const [open, setOpen] = useState(false);
  const [audioText, setAudioText] = useState(text);
  const [voice, setVoice] = useState<TVoice>(voices[0]);
  const [voiceList, setVoiceList] = useState<TVoice[]>(voices);

  // const [voiceProvider, setVoiceProvider] = useState("openai");
  const { t } = useTranslation();

  const { socket } = useStore((state) => ({
    socket: state.socket,
  }));

  useEffect(() => {
    setAudioText(text);
  }, [text]);

  useEffect(() => {
    const fetchVoices = async () => {
      const voices = await getUserVoices();
      setVoiceList((prev) => removeDuplicateVoices([...prev, ...voices]));
    };
    fetchVoices();
  }, []);

  const addElevenVoice = (id: string, name: string) => {
    setVoiceList((prev) => {
      const newvoices = [
        ...prev,
        {
          provider: "elevenlabs",
          id: id,
          name: name,
        },
      ];
      updateUserVoices(fixVoices(newvoices));
      return newvoices;
    });
  };

  const generateSpeech = async () => {
    toast.success(t("generating-speech"));

    if (voice.provider === "elevenlabs") {
      const res = await generateAudio({
        text: audioText,
        voice,
        message_id: messageId,
      });
      console.log(res);
    } else {
      socket.emit("speech_request", {
        text: audioText,

        id: messageId,
        voice,
      });
    }
    setOpen(false);
  };

  return (
    <>
      <SvgButton
        size="big"
        text={t("generate-speech")}
        svg={<Icon name="Volume2" size={20} />}
        extraClass="active-on-hover pressable border-active"
        onClick={() => setOpen(true)}
      />
      <Modal
        header={<h3 className="padding-medium ">{t("generate-speech")}</h3>}
        visible={open}
        hide={() => setOpen(false)}
      >
        <div className="flex-y gap-medium align-center">
          <Textarea
            name="text"
            extraClass="w-100"
            defaultValue={audioText}
            onChange={(value) => setAudioText(value)}
            label={t("enter-text-to-generate-audio")}
          />
          <div className="flex-x gap-medium align-center">
            <select
              className="input padding-medium"
              value={voice.id}
              onChange={(e) =>
                setVoice(voiceList.find((v) => v.id === e.target.value)!)
              }
            >
              {voiceList.map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.name}{" "}
                  <span className="text-gray">({voice.provider})</span>
                </option>
              ))}
            </select>
            <AddElevenVoice addElevenVoice={addElevenVoice} />
          </div>

          <SvgButton
            extraClass="active-on-hover pressable border-active"
            size="big"
            text={t("generate")}
            onClick={generateSpeech}
          />
        </div>
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
      <SvgButton
        extraClass="active-on-hover pressable "
        text={t("add-elevenlabs-voice")}
        svg={<Icon name="Plus" size={20} />}
        onClick={() => setOpen(true)}
      />
      <Modal
        header={
          <h3 className="padding-medium ">{t("add-elevenlabs-voice")}</h3>
        }
        visible={open}
        hide={() => setOpen(false)}
      >
        <div className="flex-y gap-medium align-center">
          <form
            onSubmit={handleSubmit}
            className="flex-y gap-medium align-center w-100"
          >
            <input
              name="voice_id"
              type="text"
              className="input w-100"
              placeholder={t("enter-voice-id")}
            />
            <input
              name="voice_name"
              type="text"
              className="input w-100"
              placeholder={t("enter-voice-name")}
            />
            <SvgButton
              extraClass="active-on-hover pressable "
              text={t("add-elevenlabs-voice")}
              svg={<Icon name="Plus" size={20} />}
              type="submit"
            />
          </form>
        </div>
      </Modal>
    </>
  );
};
