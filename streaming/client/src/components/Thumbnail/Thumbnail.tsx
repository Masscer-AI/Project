import React from "react";
import { SVGS } from "../../assets/svgs";
import { useStore } from "../../modules/store";

interface ThumbnailProps {
  src: string;
  type: string;
  name: string;
  index: number;
}

export const Thumbnail = ({ src, type, name, index }: ThumbnailProps) => {
  const { deleteAttachment } = useStore((state) => ({
    deleteAttachment: state.deleteAttachment,
  }));

  return (
    <div className="thumbnail">
      {type.indexOf("image") === 0 ? (
        <img src={src} alt={`attachment-${name}`} />
      ) : (
        <div title={name} className="file-icon">
          {SVGS.document}
        </div>
      )}

      <div className="floating-buttons">
        <button onClick={() => deleteAttachment(index)}>Clean</button>
      </div>
    </div>
  );
};
