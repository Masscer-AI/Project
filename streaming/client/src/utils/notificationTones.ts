/** Built-in notification tone definitions (must match server tone refs). */

export const NOTIFICATION_TONE_REFS = [
  "chime_success_ascending",
  "chime_error_descending",
  "magic_notification_riser",
  "magic_ascending_three_1",
  "magic_ascending_three_2",
  "magic_ascending_three_3",
  "magic_ascending_three_4",
  "magic_descending_two",
  "error_beep_short",
  "error_sharp_high",
  "error_descending_two_a",
  "error_descending_two_b",
] as const;

export type NotificationToneRef = (typeof NOTIFICATION_TONE_REFS)[number];

export type NotificationToneStep = {
  frequency: number;
  start: number;
  duration: number;
};

/** Synthesized Web Audio steps (no asset file). */
export const NOTIFICATION_TONES: Partial<
  Record<NotificationToneRef, NotificationToneStep[]>
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

/** Sample filenames under `public/sounds/` (Vite copies to dist root). */
export const NOTIFICATION_TONE_SAMPLES: Partial<
  Record<NotificationToneRef, string>
> = {
  magic_notification_riser: "magic_notification_riser.wav",
  magic_ascending_three_1: "magic_ascending_three_1.wav",
  magic_ascending_three_2: "magic_ascending_three_2.wav",
  magic_ascending_three_3: "magic_ascending_three_3.wav",
  magic_ascending_three_4: "magic_ascending_three_4.wav",
  magic_descending_two: "magic_descending_two.wav",
  error_beep_short: "error_beep_short.wav",
  error_sharp_high: "error_sharp_high.wav",
  error_descending_two_a: "error_descending_two_a.wav",
  error_descending_two_b: "error_descending_two_b.wav",
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
  {
    ref: "magic_notification_riser",
    labelKey: "notification-tone-magic-notification-riser",
    kind: "success",
  },
  {
    ref: "magic_ascending_three_1",
    labelKey: "notification-tone-magic-ascending-three-1",
    kind: "success",
  },
  {
    ref: "magic_ascending_three_2",
    labelKey: "notification-tone-magic-ascending-three-2",
    kind: "success",
  },
  {
    ref: "magic_ascending_three_3",
    labelKey: "notification-tone-magic-ascending-three-3",
    kind: "success",
  },
  {
    ref: "magic_ascending_three_4",
    labelKey: "notification-tone-magic-ascending-three-4",
    kind: "success",
  },
  {
    ref: "magic_descending_two",
    labelKey: "notification-tone-magic-descending-two",
    kind: "success",
  },
  {
    ref: "error_beep_short",
    labelKey: "notification-tone-error-beep-short",
    kind: "error",
  },
  {
    ref: "error_sharp_high",
    labelKey: "notification-tone-error-sharp-high",
    kind: "error",
  },
  {
    ref: "error_descending_two_a",
    labelKey: "notification-tone-error-descending-two-a",
    kind: "error",
  },
  {
    ref: "error_descending_two_b",
    labelKey: "notification-tone-error-descending-two-b",
    kind: "error",
  },
];

export function isNotificationToneRef(value: string): value is NotificationToneRef {
  return (NOTIFICATION_TONE_REFS as readonly string[]).includes(value);
}

/** Absolute URL for a sample under `/sounds/…` (main app + widget host). */
export function notificationToneSampleUrl(filename: string): string {
  const streamingBase =
    typeof window !== "undefined"
      ? (window as Window & { WIDGET_STREAMING_URL?: string }).WIDGET_STREAMING_URL
      : undefined;

  if (streamingBase) {
    const origin = streamingBase.replace(/\/?$/, "/");
    return new URL(`sounds/${filename}`, origin).href;
  }

  const base = import.meta.env.BASE_URL || "/";
  const normalized = base.endsWith("/") ? base : `${base}/`;
  return `${normalized}sounds/${filename}`;
}
