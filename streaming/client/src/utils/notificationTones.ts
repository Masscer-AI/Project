/** Built-in notification tone definitions (must match server tone refs). */

export const NOTIFICATION_TONE_REFS = [
  "chime_success_ascending",
  "chime_error_descending",
] as const;

export type NotificationToneRef = (typeof NOTIFICATION_TONE_REFS)[number];

export type NotificationToneStep = {
  frequency: number;
  start: number;
  duration: number;
};

export const NOTIFICATION_TONES: Record<
  NotificationToneRef,
  NotificationToneStep[]
> = {
  chime_success_ascending: [
    { frequency: 523.25, start: 0, duration: 0.1 },
    { frequency: 659.25, start: 0.09, duration: 0.16 },
  ],
  chime_error_descending: [
    { frequency: 330, start: 0, duration: 0.14 },
    { frequency: 262, start: 0.11, duration: 0.22 },
  ],
};

export const NOTIFICATION_TONE_CATALOG: {
  ref: NotificationToneRef;
  labelKey: string;
  kind: "success" | "error";
}[] = [
  {
    ref: "chime_success_ascending",
    labelKey: "notification-tone-chime-success-ascending",
    kind: "success",
  },
  {
    ref: "chime_error_descending",
    labelKey: "notification-tone-chime-error-descending",
    kind: "error",
  },
];

export function isNotificationToneRef(value: string): value is NotificationToneRef {
  return (NOTIFICATION_TONE_REFS as readonly string[]).includes(value);
}
