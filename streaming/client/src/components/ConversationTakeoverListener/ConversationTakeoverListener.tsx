import React, { useEffect } from "react";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { playNotificationSound } from "../../utils/notificationSound";

type TakeoverSocketPayload = {
  conversation_id?: string;
  message_id?: number;
  operator_user_id?: number;
  action?: string;
};

type RedisNotification<T> = {
  route_id?: string;
  event_type?: string;
  message?: T;
};

/**
 * Refreshes the open conversation when human takeover or direct messages change.
 */
export const ConversationTakeoverListener = () => {
  const { t } = useTranslation();
  const { socket, conversation, setConversation } = useStore((state) => ({
    socket: state.socket,
    conversation: state.conversation,
    setConversation: state.setConversation,
  }));

  useEffect(() => {
    const refreshIfCurrent = (raw: RedisNotification<TakeoverSocketPayload>) => {
      const data = raw?.message;
      const convId = data?.conversation_id;
      if (!data || !convId || !conversation?.id || convId !== conversation.id) {
        return;
      }
      void setConversation(conversation.id);
    };

    const handleInbound = (raw: RedisNotification<TakeoverSocketPayload>) => {
      const data = raw?.message;
      const convId = data?.conversation_id;
      if (!data || !convId || !conversation?.id || convId !== conversation.id) {
        return;
      }
      toast(t("human-takeover-inbound-toast"), { icon: "💬" });
      playNotificationSound("success");
      void setConversation(conversation.id);
    };

    const handleTakeoverUpdated = (
      raw: RedisNotification<TakeoverSocketPayload>
    ) => {
      refreshIfCurrent(raw);
    };

    socket.on("conversation_takeover_updated", handleTakeoverUpdated);
    socket.on("conversation_message_created", refreshIfCurrent);
    socket.on("conversation_takeover_inbound", handleInbound);

    return () => {
      socket.off("conversation_takeover_updated", handleTakeoverUpdated);
      socket.off("conversation_message_created", refreshIfCurrent);
      socket.off("conversation_takeover_inbound", handleInbound);
    };
  }, [conversation?.id, setConversation, socket, t]);

  return null;
};
