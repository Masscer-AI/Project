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
};

export const Modal = ({
  children,
  hide,
  visible = true,
  extraButtons = null,
  minHeight = "50vh",
}: TModalProps) => {
  if (!visible) return null;

  return createPortal(
    <div className={styles.modalComponent}>
      <div className={styles.modalBackdrop} onClick={hide}></div>
      <div className={styles.modalContent}>
        {children}
        <div className="d-flex justify-end modal-closer">
          {extraButtons}
          <SvgButton onClick={hide} svg={SVGS.close} />
        </div>
      </div>
    </div>,
    document.body
  );
};
