import {
  NOTIFICATION_TONES,
  NotificationToneRef,
  isNotificationToneRef,
} from "./notificationTones";

export type NotificationSoundKind = "success" | "error";

export type TNotificationSettings = {
  activated: boolean;
  volume: number;
  success_tone_ref: NotificationToneRef;
  failure_tone_ref: NotificationToneRef;
};

export const DEFAULT_NOTIFICATION_SETTINGS: TNotificationSettings = {
  activated: true,
  volume: 0.12,
  success_tone_ref: "chime_success_ascending",
  failure_tone_ref: "chime_error_descending",
};

let activeSettings: TNotificationSettings = { ...DEFAULT_NOTIFICATION_SETTINGS };

let audioContext: AudioContext | null = null;
let unlockListenersAttached = false;
let lastErrorSoundAt = 0;

const ERROR_DEBOUNCE_MS = 800;

function mergeNotificationSettings(
  partial: Partial<TNotificationSettings> | null | undefined
): TNotificationSettings {
  if (!partial) return { ...DEFAULT_NOTIFICATION_SETTINGS };
  const merged = { ...DEFAULT_NOTIFICATION_SETTINGS, ...partial };
  return {
    activated: Boolean(merged.activated),
    volume: Math.min(1, Math.max(0, Number(merged.volume) || 0)),
    success_tone_ref: isNotificationToneRef(merged.success_tone_ref)
      ? merged.success_tone_ref
      : DEFAULT_NOTIFICATION_SETTINGS.success_tone_ref,
    failure_tone_ref: isNotificationToneRef(merged.failure_tone_ref)
      ? merged.failure_tone_ref
      : DEFAULT_NOTIFICATION_SETTINGS.failure_tone_ref,
  };
}

/** Keep in sync with user preferences from the store (or defaults for anonymous/widget). */
export function syncNotificationSoundSettings(
  settings: Partial<TNotificationSettings> | null | undefined
): void {
  activeSettings = mergeNotificationSettings(settings);
}

export function getNotificationSoundSettings(): TNotificationSettings {
  return { ...activeSettings };
}

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;

  if (!audioContext) {
    const Ctx =
      window.AudioContext ||
      (window as Window & { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!Ctx) return null;
    audioContext = new Ctx();
  }

  return audioContext;
}

function attachUnlockListeners() {
  if (unlockListenersAttached || typeof window === "undefined") return;
  unlockListenersAttached = true;

  const unlock = () => {
    const ctx = getAudioContext();
    if (ctx?.state === "suspended") {
      void ctx.resume();
    }
  };

  window.addEventListener("pointerdown", unlock, { once: true, passive: true });
  window.addEventListener("keydown", unlock, { once: true });
}

function playToneSteps(
  toneRef: NotificationToneRef,
  volume: number,
  tones = NOTIFICATION_TONES[toneRef]
) {
  if (!tones?.length || volume <= 0) return;

  const ctx = getAudioContext();
  if (!ctx) return;

  attachUnlockListeners();

  if (ctx.state === "suspended") {
    void ctx.resume();
  }

  const base = ctx.currentTime;

  for (const { frequency, start, duration } of tones) {
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();

    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    oscillator.connect(gain);
    gain.connect(ctx.destination);

    const t0 = base + start;
    const t1 = t0 + duration;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(volume, t0 + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t1);

    oscillator.start(t0);
    oscillator.stop(t1 + 0.02);
  }
}

function resolveToneRef(
  kind: NotificationSoundKind,
  settings: TNotificationSettings
): NotificationToneRef {
  return kind === "success"
    ? settings.success_tone_ref
    : settings.failure_tone_ref;
}

function playWithSettings(
  kind: NotificationSoundKind,
  settings: TNotificationSettings
) {
  if (!settings.activated || settings.volume <= 0) return;

  const toneRef = resolveToneRef(kind, settings);
  playToneSteps(toneRef, settings.volume);
}

/**
 * Short UI feedback tones (Web Audio — no asset files).
 * Errors are debounced so paired agent_events + agent_loop_finished do not double-play.
 */
export function playNotificationSound(kind: NotificationSoundKind): void {
  if (kind === "error") {
    const now = Date.now();
    if (now - lastErrorSoundAt < ERROR_DEBOUNCE_MS) return;
    lastErrorSoundAt = now;
  }

  playWithSettings(kind, activeSettings);
}

/** Preview from Settings UI (uses draft values, ignores master activated for preview). */
export function previewNotificationSound(
  kind: NotificationSoundKind,
  settings: Partial<TNotificationSettings>
): void {
  const merged = mergeNotificationSettings(settings);
  playWithSettings(kind, { ...merged, activated: true });
}
