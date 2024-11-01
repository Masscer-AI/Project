import React from "react";
import styles from "./modal.module.css";
import { createPortal } from "react-dom";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

export const Modal = ({ children, hide, visible = true, minHeight }) => {
  if (!visible) return null;

  return createPortal(
    <div className={styles.modalComponent}>
      <div className={styles.modalBackdrop} onClick={hide}></div>
      <div className={styles.modalContent} style={{ minHeight }}>
        <SvgButton extraClass="modal-closer" onClick={hide} svg={SVGS.close} />
        <div style={{ minHeight }}>{children}</div>
      </div>
    </div>,
    document.body
  );
};
