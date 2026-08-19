export const VITE_GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

export const hasGoogleOAuthClientId = VITE_GOOGLE_CLIENT_ID.trim().length > 0;
