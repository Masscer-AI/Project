export const NOTIFICATIONS_INBOX_UPDATED_EVENT = "masscer:notifications-updated";

/** Bump unread badge + inbox lists after a new notification arrives or read state changes. */
export function notifyInboxUpdated(): void {
  window.dispatchEvent(new CustomEvent(NOTIFICATIONS_INBOX_UPDATED_EVENT));
}
