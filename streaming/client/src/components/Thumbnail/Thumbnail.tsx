import React from "react";
import { SVGS } from "../../assets/svgs";
import { useStore } from "../../modules/store";

export const Thumbnail = ({ src, type, name, index }) => {
  const { deleteAttachment } = useStore((state) => ({
    deleteAttachment: state.deleteAttachment,
  }));

  return (
    <div className="thumbnail">
      {type.indexOf("image") === 0 ? (
        <img src={src} alt={`attachment-${name}`} />
      ) : (
        <div className="file-icon">{SVGS.document}</div>
      )}

      <div className="floating-buttons">
        <button onClick={() => deleteAttachment(index)}>Clean</button>
        <button>Persist</button>
      </div>
    </div>
  );
};
