import React, { useState } from "react";
import { SVGS } from "../../assets/svgs";
import { useStore } from "../../modules/store";
import { SvgButton } from "../SvgButton/SvgButton";
import { useTranslation } from "react-i18next";
import { Modal } from "../Modal/Modal";
interface ThumbnailProps {
  src: string;
  type: string;
  name: string;
  index: number;
  showFloatingButtons?: boolean;
}

export const Thumbnail = ({
  src,
  type,
  name,
  index,
  showFloatingButtons = false,
}: ThumbnailProps) => {
  const [showModal, setShowModal] = useState(false);

  const { t } = useTranslation();
  const { deleteAttachment } = useStore((state) => ({
    deleteAttachment: state.deleteAttachment,
  }));

  return (
    <>
      {showModal && (
        <ImageModal src={src} name={name} hide={() => setShowModal(false)} />
      )}
      <div className="thumbnail pointer">
        {type.indexOf("image") === 0 && (
          <img
            onClick={() => setShowModal(true)}
            src={src}
            alt={`attachment-${name}`}
          />
        )}
        {type.indexOf("audio") === 0 && (
          <>
            <SvgButton />
            <audio src={src} playsInline />
          </>
        )}
        {type.indexOf("audio") !== 0 && type.indexOf("image") !== 0 && (
          <div title={name} className="file-icon">
            {SVGS.document}
          </div>
        )}
        {showFloatingButtons && (
          <div className="floating-buttons">
            <SvgButton
              title={t("delete")}
              svg={SVGS.trash}
              extraClass="bg-danger square-button"
              onClick={() => deleteAttachment(index)}
            />
          </div>
        )}
      </div>
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
  const handleDownload = () => {
    const a = document.createElement("a");
    a.href = src;
    a.setAttribute("download", name);
    a.setAttribute("target", "_blank");
    a.click();
  };

  return (
    <Modal
      minHeight={"50vh"}
      hide={hide}
      extraButtons={
        <SvgButton
          onClick={handleDownload}
          title="Download"
          svg={SVGS.download}
        />
      }
    >
      <div className="d-flex justify-center align-center ">
        <img style={{ width: "100%" }} src={src} alt={`attachment-${name}`} />
      </div>
    </Modal>
  );
};
