export const NOTIFICATIONS_INBOX_UPDATED_EVENT = "masscer:notifications-updated";

export function notifyInboxUpdated(): void {
  window.dispatchEvent(new CustomEvent(NOTIFICATIONS_INBOX_UPDATED_EVENT));
}
