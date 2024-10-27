import React from "react";
import styles from "./modal.module.css";
import { createPortal } from "react-dom";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

export const Modal = ({ children, hide, visible = true }) => {
  if (!visible) return null;

  return createPortal(
    <div className={styles.modalComponent}>
      <div className={styles.modalBackdrop} onClick={hide}></div>
      <div className={styles.modalContent}>
        <SvgButton extraClass="modal-closer" onClick={hide} svg={SVGS.close} />
        <div>{children}</div>
      </div>
    </div>,
    document.body
  );
};
