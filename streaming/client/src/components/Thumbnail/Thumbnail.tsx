import React from "react";
import { SVGS } from "../../assets/svgs";
import { useStore } from "../../modules/store";
import { uploadDocument } from "../../modules/apiCalls";
import toast from "react-hot-toast";

export const Thumbnail = ({ src, type, name, index, file }) => {
  const { deleteAttachment, chatState } = useStore((state) => ({
    deleteAttachment: state.deleteAttachment,
    chatState: state.chatState,
  }));

  const persistDocumentInDB = async () => {
    const formData = new FormData();
    formData.append("agent_slug", chatState.selectedAgent);
    formData.append("name", name);
    formData.append("file", file);
    console.log("FILE BEING APPENDED", file);

    try {
      const res = await uploadDocument(formData);
      console.log(res, "STATUS RECEIVED");

      if ("id" in res) {
        toast.success("File persisted in the memory of your agent!");
      } else {
        console.log(res);
        toast.error("Failed to persist the file.");
      }
    } catch (error) {
      toast.error(error.response.data.error);
    }
  };

  return (
    <div className="thumbnail">
      {type.indexOf("image") === 0 ? (
        <img src={src} alt={`attachment-${name}`} />
      ) : (
        <div className="file-icon">{SVGS.document}</div>
      )}

      <div className="floating-buttons">
        <button onClick={() => deleteAttachment(index)}>Clean</button>
        <button onClick={persistDocumentInDB}>Persist</button>
      </div>
    </div>
  );
};
