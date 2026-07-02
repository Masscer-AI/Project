import React, { useEffect, useRef, useState } from "react";
import { useGoogleLogin, useGoogleOAuth } from "@react-oauth/google";
import { useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Alert, Anchor, Button, Loader, Stack, Text, Title } from "@mantine/core";
import { IconBrandGoogle } from "@tabler/icons-react";
import {
  clearGoogleHandoffSession,
  getGoogleAuthRedirectUri,
  loadGoogleHandoffSession,
  isGoogleCodeExchangeDone,
  markGoogleCodeExchangeDone,
  postGoogleAuthAndHandoff,
  redirectToTenantHandoff,
  releaseGoogleCodeExchangeLock,
  saveGoogleHandoffSession,
  tryAcquireGoogleCodeExchangeLock,
} from "../../../utils/googleAuthHandoff";

export default function AuthGoogleBridge() {
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const { scriptLoadedSuccessfully } = useGoogleOAuth();
  const [error, setError] = useState<string | null>(null);
  const [isRedirecting, setIsRedirecting] = useState(true);
  const startedRedirectRef = useRef(false);

  const startGoogleRedirect = useGoogleLogin({
    flow: "auth-code",
    ux_mode: "redirect",
    redirect_uri: getGoogleAuthRedirectUri(),
  });

  useEffect(() => {
    const oauthError = searchParams.get("error");
    if (oauthError) {
      setError(t("an-error-occurred"));
      setIsRedirecting(false);
      return;
    }

    const code = searchParams.get("code");
    if (code) {
      if (!tryAcquireGoogleCodeExchangeLock(code)) {
        return;
      }

      void (async () => {
        const session = loadGoogleHandoffSession();
        if (!session) {
          releaseGoogleCodeExchangeLock(code);
          setError(t("an-error-occurred"));
          setIsRedirecting(false);
          return;
        }

        try {
          const data = await postGoogleAuthAndHandoff({
            code,
            redirect_uri: getGoogleAuthRedirectUri(),
            return_to: session.returnTo,
          });
          markGoogleCodeExchangeDone(code);
          clearGoogleHandoffSession();
          redirectToTenantHandoff(data.handoff_code, data.return_to, session.next);
        } catch (err: unknown) {
          if (isGoogleCodeExchangeDone(code)) {
            return;
          }
          releaseGoogleCodeExchangeLock(code);
          const axiosErr = err as { response?: { data?: { error?: string } } };
          setError(axiosErr.response?.data?.error || t("an-error-occurred"));
          setIsRedirecting(false);
        }
      })();
      return;
    }

    const returnTo = searchParams.get("return_to");
    if (!returnTo) {
      setError(t("an-error-occurred"));
      setIsRedirecting(false);
      return;
    }

    saveGoogleHandoffSession({
      returnTo,
      next: searchParams.get("next"),
    });

    if (!scriptLoadedSuccessfully || startedRedirectRef.current) {
      return;
    }
    startedRedirectRef.current = true;
    startGoogleRedirect();
  }, [searchParams, scriptLoadedSuccessfully, startGoogleRedirect, t]);

  const handleRetry = () => {
    const session = loadGoogleHandoffSession();
    const returnTo = searchParams.get("return_to") || session?.returnTo;
    if (!returnTo) {
      setError(t("an-error-occurred"));
      return;
    }
    saveGoogleHandoffSession({
      returnTo,
      next: searchParams.get("next") ?? session?.next ?? null,
    });
    setError(null);
    setIsRedirecting(true);
    startedRedirectRef.current = false;
    startGoogleRedirect();
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)] p-8">
      <Stack align="center" gap="md" maw={360}>
        <Title order={3} ta="center">
          {t("login")}
        </Title>
        {error ? (
          <>
            <Alert color="red" variant="light">
              {error}
            </Alert>
            <Button
              leftSection={<IconBrandGoogle size={18} />}
              onClick={handleRetry}
              fullWidth
            >
              Continue with Google
            </Button>
            <Text ta="center" size="sm">
              <Anchor component={Link} to="/login">
                {t("login")}
              </Anchor>
            </Text>
          </>
        ) : (
          <>
            <Loader color="violet" />
            <Text size="sm" c="dimmed" ta="center">
              {isRedirecting ? "Signing in with Google…" : t("successfully-logged-in")}
            </Text>
          </>
        )}
      </Stack>
    </div>
  );
}
