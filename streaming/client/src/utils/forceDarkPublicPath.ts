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
