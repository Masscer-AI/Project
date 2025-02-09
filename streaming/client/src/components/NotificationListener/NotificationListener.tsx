import React, { useEffect } from "react";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
// import toast from "react-hot-toast";
// import { useTranslation } from "react-i18next";

export const NotificationListener = () => {
  const { t } = useTranslation();
  const { socket, setConversation, conversation } = useStore((state) => ({
    socket: state.socket,
    setConversation: state.setConversation,
    conversation: state.conversation,
  }));

  useEffect(() => {
    socket.on("video_generated", () => {
      toast.success(t("video-generated-successfully"));
      setConversation(conversation?.id);
    });

    socket.on("out_of_balance", (data) => {
      // toast.error(t("out-of-compute-units"));
      console.log("out of balance", data);
    });

    socket.on("audio_generated", () => {
      toast.success(t("audio-generated-successfully"));
      setConversation(conversation?.id);
    });

    return () => {
      socket.off("video_generated");
      socket.off("out_of_balance");
      socket.off("audio_generated");
    };
  }, [conversation]);
  return <></>;
};
