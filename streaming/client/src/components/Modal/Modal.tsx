import React from "react";
import styles from "./modal.module.css";
import { createPortal } from "react-dom";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

type TModalProps = {
  children: React.ReactNode;
  hide: () => void;
  visible?: boolean;
  extraButtons?: React.ReactNode;
  minHeight?: string;
  header?: React.ReactNode;
};

export const Modal = ({
  children,
  hide,
  visible = true,
  extraButtons = null,
  minHeight = "50vh",
  header = null,
}: TModalProps) => {
  if (!visible) return null;

  return createPortal(
    <div className={styles.modalComponent}>
      <div className={styles.modalBackdrop} onClick={hide}></div>
      <div className={styles.modalContent} style={{ minHeight }}>
        <div className="d-flex justify-end modal-closer gap-small">
          {extraButtons}
          <SvgButton
            extraClass="pressable bg-danger "
            onClick={hide}
            svg={SVGS.close}
          />
        </div>

        {header && <section className={styles.header}>{header}</section>}
        <section className={styles.content}>{children}</section>
      </div>
    </div>,
    document.body
  );
};
