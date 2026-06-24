import React, { useEffect } from "react";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { playNotificationSound } from "../../utils/notificationSound";

export const NotificationListener = () => {
  const { t } = useTranslation();
  const { socket, setConversation, conversation } = useStore((state) => ({
    socket: state.socket,
    setConversation: state.setConversation,
    conversation: state.conversation,
  }));

  useEffect(() => {
    socket.on("video_generated", () => {
      playNotificationSound("success");
      toast.success(t("video-generated-successfully"));
      setConversation(conversation?.id);
    });

    socket.on("out_of_balance", (data) => {
      playNotificationSound("error");
      // toast.error(t("out-of-compute-units"));
      console.log("out of balance", data);
    });

    socket.on("subscription_expired_with_purchased_locked", () => {
      toast(t("subscription-expired-with-purchased-locked-toast"), { icon: "ℹ️" });
    });

    socket.on("audio_generated", () => {
      playNotificationSound("success");
      toast.success(t("audio-generated-successfully"));
      setConversation(conversation?.id);
    });

    socket.on("data_export_ready", (data: { job_id?: string }) => {
      playNotificationSound("success");
      toast.success(t("data-export-ready-toast"));
      window.dispatchEvent(
        new CustomEvent("masscer:data-export-ready", { detail: data })
      );
    });

    return () => {
      socket.off("video_generated");
      socket.off("out_of_balance");
      socket.off("subscription_expired_with_purchased_locked");
      socket.off("audio_generated");
      socket.off("data_export_ready");
    };
  }, [conversation, setConversation, socket, t]);
  return <></>;
};
