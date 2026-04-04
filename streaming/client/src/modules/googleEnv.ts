/** Set at build time (Vite). Empty in production if the Docker build omits VITE_GOOGLE_CLIENT_ID. */
export const VITE_GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

export const hasGoogleOAuthClientId = VITE_GOOGLE_CLIENT_ID.trim().length > 0;
