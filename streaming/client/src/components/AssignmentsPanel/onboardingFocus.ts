const HIGHLIGHT_CLASS = "onboarding-focus-highlight";
const HIGHLIGHT_MS = 2600;

/**
 * Find an element marked with data-onboarding-target="<key>", scroll it into
 * view and highlight it briefly. Polls a few times so it works right after a
 * route change (element may not be mounted yet).
 */
export function focusOnboardingTarget(
  key: string,
  { attempts = 20, intervalMs = 150 }: { attempts?: number; intervalMs?: number } = {}
): Promise<boolean> {
  const selector = `[data-onboarding-target="${CSS.escape(key)}"]`;

  return new Promise((resolve) => {
    let remaining = attempts;

    const tryFocus = () => {
      const el = document.querySelector<HTMLElement>(selector);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add(HIGHLIGHT_CLASS);
        window.setTimeout(() => {
          el.classList.remove(HIGHLIGHT_CLASS);
        }, HIGHLIGHT_MS);
        resolve(true);
        return;
      }
      remaining -= 1;
      if (remaining <= 0) {
        resolve(false);
        return;
      }
      window.setTimeout(tryFocus, intervalMs);
    };

    tryFocus();
  });
}
