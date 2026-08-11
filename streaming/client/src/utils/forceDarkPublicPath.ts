/**
 * Public surfaces designed with hardcoded dark backgrounds (landing, auth).
 * When the OS/user theme is light, Mantine text + CSS vars go dark-on-dark —
 * force dark scheme on these paths so contrast stays correct.
 */
const FORCE_DARK_EXACT = new Set([
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/auth/callback",
  "/auth/google",
]);

export function isForceDarkPublicPath(pathname: string): boolean {
  return FORCE_DARK_EXACT.has(pathname);
}
