import React from "react";
import { SVGS } from "../../assets/svgs";

export const Thumbnail = ({ src, type }) => {
  return (
    <div className="thumbnail">
      {type.indexOf("image") === 0 ? (
        <img src={src} alt={`attachment-${name}`} />
      ) : (
        <div className="file-icon">{SVGS.document}</div>
      )}
    </div>
  );
};
