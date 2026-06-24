import { useEffect } from "react";
import toast from "react-hot-toast";
import { useStore } from "../../modules/store";
import { TUserNotification } from "../../types";
import { notifyInboxUpdated } from "../../utils/notificationInboxEvents";
import { playNotificationSound } from "../../utils/notificationSound";

type InAppNotificationSocketPayload = {
  route_id?: string;
  user_id?: number;
  event_type?: string;
  message?: TUserNotification;
};

/**
 * Real-time push when a UserNotification row is created (alert → notification rule).
 * Replaces slow poll-only discovery for the inbox badge and list.
 */
export function InAppNotificationListener() {
  const socket = useStore((s) => s.socket);

  useEffect(() => {
    const handleCreated = (raw: InAppNotificationSocketPayload) => {
      const notification = raw?.message;
      if (!notification?.id) return;

      playNotificationSound("success");
      notifyInboxUpdated();

      const preview =
        notification.message.length > 160
          ? `${notification.message.slice(0, 157)}…`
          : notification.message;
      toast(preview, { icon: "🔔" });
    };

    socket.on("in_app_notification_created", handleCreated);

    return () => {
      socket.off("in_app_notification_created", handleCreated);
    };
  }, [socket]);

  return null;
}
