import React from "react";
import styles from "./Modal.module.css";

export const Modal = ({ children }) => {
  return (
    <div className="modal-component">
      <div className={styles.modalBackdrop}></div>
      <div className="modal-content">{children}</div>
    </div>
  );
};
