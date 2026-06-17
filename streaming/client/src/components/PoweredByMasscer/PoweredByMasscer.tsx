import React from "react";
import { MASSCER_WHATSAPP_URL } from "../../modules/constants";
import "./PoweredByMasscer.css";

type Props = {
  className?: string;
  style?: React.CSSProperties;
};

export const PoweredByMasscer: React.FC<Props> = ({ className, style }) => (
  <p className={className} style={style}>
    Powered by{" "}
    <a
      href={MASSCER_WHATSAPP_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="powered-by-masscer-link"
    >
      <strong>Masscer AI</strong>
    </a>
  </p>
);
