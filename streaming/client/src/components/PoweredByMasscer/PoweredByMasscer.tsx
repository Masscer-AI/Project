import React from "react";
import { MASSCER_WHATSAPP_URL } from "../../modules/constants";
import { useStore } from "../../modules/store";
import "./PoweredByMasscer.css";

type Props = {
  className?: string;
  style?: React.CSSProperties;
};

export const PoweredByMasscer: React.FC<Props> = ({ className, style }) => {
  const hidePoweredBy = useStore((s) => s.tenantBranding?.hide_powered_by);
  if (hidePoweredBy) return null;

  return (
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
};
