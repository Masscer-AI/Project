import React, { useEffect, useState } from "react";
import { SVGS } from "../../assets/svgs";
import { useStore } from "../../modules/store";
import { SvgButton } from "../SvgButton/SvgButton";
import { useTranslation } from "react-i18next";
import { Modal } from "../Modal/Modal";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import { SliderInput } from "../SimpleForm/SliderInput";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { AttatchmentMode } from "../../types";
import { Textarea } from "../SimpleForm/Textarea";
import toast from "react-hot-toast";
import { generateVideo } from "../../modules/apiCalls";
import { Select } from "../SimpleForm/Select";
import { AspectRatio } from "../ImageGenerator/ImageGenerator";

interface ThumbnailProps {
  id?: number;
  src: string;
  type: string;
  name: string;
  index: number;
  showFloatingButtons?: boolean;
  mode?: AttatchmentMode;
  message_id?: number;
}

export const Thumbnail = ({
  id,
  src,
  type,
  name,
  index,
  showFloatingButtons = false,
  mode,
  message_id,
}: ThumbnailProps) => {
  const { t } = useTranslation();
  const { deleteAttachment } = useStore((state) => ({
    deleteAttachment: state.deleteAttachment,
  }));

  return (
    <>
      {type.indexOf("audio") !== 0 && type.indexOf("image") !== 0 && (
        <DocumentThumnail
          id={id}
          index={index}
          onDelete={() => deleteAttachment(index)}
          type={type}
          name={name}
          showFloatingButtons={showFloatingButtons}
          mode={mode}
        />
      )}
      {type.indexOf("image") === 0 && (
        <div className="thumbnail pointer ">
          <ImageThumbnail
            src={src}
            message_id={message_id}
            name={name}
            buttons={
              showFloatingButtons && (
                <div className="d-flex align-center justify-center padding-small">
                  <SvgButton
                    title={t("delete")}
                    svg={SVGS.trash}
                    extraClass="danger-on-hover "
                    confirmations={[`${t("sure")}`]}
                    onClick={() => deleteAttachment(index)}
                  />
                </div>
              )
            }
          />
        </div>
      )}
      {type.indexOf("audio") === 0 && (
        <div className="thumbnail pointer">
          <SvgButton />
          <audio src={src} playsInline />
        </div>
      )}
    </>
  );
};

const aspectRatioOptions = [
  { label: "1280:768", value: "1280:768" },
  { label: "768:1280", value: "768:1280" },
];

const ImageModal = ({
  src,
  name,
  hide,
  message_id,
}: {
  src: string;
  name: string;
  hide: () => void;
  message_id?: number;
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const { t } = useTranslation();
  const [videoPrompt, setVideoPrompt] = useState("");
  const [ratio, setRatio] = useState("1280:768");

  const handleDownload = () => {
    const a = document.createElement("a");

    a.href = src.startsWith("data:") ? src : `data:image/png;base64,${src}`;
    a.setAttribute("download", name);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const toggleEdit = () => {
    setIsEditing(!isEditing);
  };

  const handleGenerateVideo = async () => {
    const response = await generateVideo({
      prompt: videoPrompt,
      image_b64: src,
      message_id: message_id!,
      ratio: ratio,
    });
    console.log(response);

    toast.success(t("video-job-started"));
  };

  return (
    <Modal
      minHeight={"50vh"}
      hide={hide}
      extraButtons={
        <>
          <SvgButton
            onClick={handleDownload}
            title="Download"
            extraClass="pressable bg-active"
            svg={SVGS.download}
          />
          <SvgButton
            onClick={toggleEdit}
            title="Edit"
            extraClass="pressable bg-active"
            svg={SVGS.edit}
          />
        </>
      }
    >
      <div className="flex-y justify-center align-center ">
        <h2>{isEditing ? t("Generate Video") : t("view")}</h2>
        {isEditing && (
          <div className="flex-y gap-small align-center w-100">
            <Textarea
              extraClass="w-100"
              onChange={(e) => setVideoPrompt(e)}
              placeholder={t("describe-the-video")}
              defaultValue={videoPrompt}
            />
            <div className="d-flex gap-small align-center w-100">
              <h4>{t("aspect-ratio")}</h4>
              {aspectRatioOptions.map((option) => (
                <AspectRatio
                  key={option.value}
                  size={option.value}
                  separator=":"
                  selected={ratio === option.value}
                  onClick={() => setRatio(option.value)}
                />
              ))}
            </div>
            <SvgButton
              onClick={handleGenerateVideo}
              title={t("generate-video")}
              svg={SVGS.addDocument}
            />
          </div>
        )}
        <img style={{ width: "100%" }} src={src} alt={`attachment-${name}`} />
      </div>
    </Modal>
  );
};

const DocumentThumnail = ({
  index,
  type,
  name,
  onDelete,
  id,
  showFloatingButtons,
  mode,
}) => {
  const { updateAttachment } = useStore((state) => ({
    updateAttachment: state.updateAttachment,
  }));
  const { t } = useTranslation();
  const [ragMode, setRagMode] = useState(
    mode ? mode : ("similar_chunks" as AttatchmentMode)
  );

  const ragModeHelpHelper = {
    similar_chunks: t("chunks-mode-help-text"),
    all_possible_text: t("all-content-mode-help-text"),
  };

  useEffect(() => {
    updateAttachment(index, { mode: ragMode });
  }, [ragMode]);

  return (
    <div
      title={name}
      className="width-150 document-attachment bg-contrast rounded padding-small "
    >
      <div className="d-flex gap-small align-center ">
        <div>{SVGS.document}</div>
        <p className="cut-text-to-line">{name}</p>

        {showFloatingButtons && (
          <FloatingDropdown
            bottom="100%"
            // right="0"
            left="50%"
            extraClass="padding-big border-secondary"
            transform="translateX(-50%)"
            opener={<SvgButton title={t("options")} svg={SVGS.options} />}
          >
            cutted-text
            <div className="d-flex gap-medium flex-y width-200 ">
              <h3 className="text-center">{t("configure")}</h3>
              <SliderInput
                extraClass="d-flex align-center rounded"
                name="rag-mode"
                labelTrue={t("similar-chunks")}
                labelFalse={t("allContent")}
                keepActive={true}
                checked={ragMode === "similar_chunks"}
                onChange={(value) => {
                  setRagMode(value ? "similar_chunks" : "all_possible_text");
                }}
              />

              <MarkdownRenderer
                extraClass="text-mini"
                markdown={ragModeHelpHelper[ragMode]}
              />
              <SvgButton
                title={t("delete")}
                size="big"
                svg={SVGS.trash}
                extraClass="bg-danger square-button pressable"
                confirmations={[`${t("sure")}`]}
                onClick={() => onDelete()}
              />
            </div>
          </FloatingDropdown>
        )}
      </div>
    </div>
  );
};

const ImageThumbnail = ({
  src,
  name,
  buttons,
  message_id,
}: {
  src: string;
  name: string;
  buttons?: React.ReactNode;
  message_id?: number;
}) => {
  const [showModal, setShowModal] = useState(false);

  return (
    <div className="thumbnail pointer">
      {showModal && (
        <ImageModal
          src={src}
          name={name}
          hide={() => setShowModal(false)}
          message_id={message_id}
        />
      )}
      <img
        onClick={() => setShowModal(true)}
        src={src}
        alt={`attachment-${name}`}
      />
      {buttons}
    </div>
  );
};
