import React from "react";
import styles from "./Loader.module.css";

export const Loader = ({ text }: { text: string }) => {
  return (
    <div className="d-flex align-center gap-big padding-big">
      <div className={styles.loader}></div>
      <div className={styles.loaderText}>{text}</div>
    </div>
  );
};
