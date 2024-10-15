import React from "react";
import { SVGS } from "../../assets/svgs";
import { useStore } from "../../modules/store";
// import { uploadDocument } from "../../modules/apiCalls";
// import toast from "react-hot-toast";

export const Thumbnail = ({ src, type, name, index, file }) => {
  const { deleteAttachment, chatState } = useStore((state) => ({
    deleteAttachment: state.deleteAttachment,
    chatState: state.chatState,
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
      </div>
    </div>
  );
};
