import React, { useEffect, useState } from "react";
import styles from "./Loader.module.css";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { SVGS } from "../../assets/svgs";

export const Loader = ({ text="..." }: { text?: string }) => {
  const [innerText, setInnerText] = useState(text);

  const { t } = useTranslation();

  const { socket } = useStore((s) => ({
    socket: s.socket,
  }));

  useEffect(() => {
    socket.on("generation_status", (data) => {
      let completeMessage = t(data.message);
      completeMessage += data.extra ? ` ${data.extra}` : "";
      setInnerText(completeMessage);
    });
    return () => {
      socket.off("generation_status");
    };
  }, [text]);

  return (
    <div className="d-flex gap-big  padding-medium align-center">
      <div className={"spinner"}></div>
      <span className="loaderText cutted-text">{innerText}</span>
    </div>
  );
};
