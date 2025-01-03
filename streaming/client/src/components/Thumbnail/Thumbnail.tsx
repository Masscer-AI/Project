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

interface ThumbnailProps {
  id?: number;
  src: string;
  type: string;
  name: string;
  index: number;
  showFloatingButtons?: boolean;
  mode?: AttatchmentMode;
}

export const Thumbnail = ({
  id,
  src,
  type,
  name,
  index,
  showFloatingButtons = false,
  mode,
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

const ImageModal = ({
  src,
  name,
  hide,
}: {
  src: string;
  name: string;
  hide: () => void;
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const { t } = useTranslation();

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
        <h2>{isEditing ? t("edit") : t("view")}</h2>
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
          >cutted-text
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
}: {
  src: string;
  name: string;
  buttons?: React.ReactNode;
}) => {
  const [showModal, setShowModal] = useState(false);

  return (
    <div className="thumbnail pointer">
      {showModal && (
        <ImageModal src={src} name={name} hide={() => setShowModal(false)} />
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
