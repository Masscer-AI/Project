import React from "react";
import styles from "./modal.module.css";

export const Modal = ({ children }) => {
  return (
    <div className="modal-component">
      <div className={styles.modalBackdrop}></div>
      <div className={styles.modalBackdrop}>{children}</div>
    </div>
  );
};
