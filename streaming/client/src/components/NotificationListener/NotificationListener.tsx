import React, { useEffect } from "react";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";

export const NotificationListener = () => {
  const { t } = useTranslation();
  const { socket } = useStore((state) => ({
    socket: state.socket,
  }));

  useEffect(() => {
    socket.on("video_generated", (data) => {
      toast.success(t("video-generated-please-reload"));
      // window.location.reload();
    });
    socket.on("out_of_balance", (data) => {
      // toast.error(t("out-of-compute-units"));
      console.log("out of balance", data);
    });
    return () => {
      socket.off("video_generated");
      socket.off("out_of_balance");
    };
  }, []);
  return <></>;
};
