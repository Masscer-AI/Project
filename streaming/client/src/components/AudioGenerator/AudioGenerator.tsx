import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { Textarea } from "../SimpleForm/Textarea";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";

const voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"];
export const AudioGenerator = ({
  messageId,
  text,
}: {
  messageId: string;
  text: string;
}) => {
  const [open, setOpen] = useState(false);
  const [audioText, setAudioText] = useState(text);
  const [voice, setVoice] = useState("alloy");
  const { t } = useTranslation();

  const { socket } = useStore((state) => ({
    socket: state.socket,
  }));

  useEffect(() => {
    setAudioText(text);
  }, [text]);

  const generateSpeech = () => {
    toast.success(t("generating-speech"));
    socket.emit("speech_request", {
      text: audioText,
      id: messageId,
      voice: {
        type: "openai",
        slug: voice,
      },
    });
  };

  return (
    <>
      <SvgButton
        size="big"
        text={t("generate-speech")}
        svg={SVGS.waves}
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
          <select
            className="input padding-medium"
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
          >
            {voices.map((voice) => (
              <option value={voice}>{voice}</option>
            ))}
          </select>
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
