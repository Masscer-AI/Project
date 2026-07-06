import React, { useEffect, useState } from "react";
import axios from "axios";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { API_URL } from "../../../modules/constants";
import { resolvePostLoginPath } from "../../../utils/loginRedirect";
import { useTranslation } from "react-i18next";
import { Alert, Anchor, Loader, Stack, Text, Title } from "@mantine/core";
import {
  AUTH_FORM_CARD_CLASS,
  AUTH_FORM_CARD_STYLE,
  AUTH_PANEL_LEFT_BACKGROUND,
} from "../../../utils/tenantTheme";
import { handleTenantPortalAccessError } from "../../../utils/tenantPortalAccess";

const panelBase = "flex-1 flex flex-col justify-center items-center p-8";
const panelLeftLayout =
  "border-r border-white/[0.06] md:min-h-0 min-h-[40vh] md:border-b-0 border-b border-white/[0.06]";
const panelRight = "bg-[var(--bg-color,#0a0a0a)] md:min-h-0 min-h-[60vh]";

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      setError(t("an-error-occurred"));
      return;
    }

    let cancelled = false;

    async function exchange() {
      try {
        const response = await axios.post(`${API_URL}/v1/auth/handoff/exchange`, {
          code,
        });
        if (cancelled) return;
        if (response.data.token) {
          localStorage.setItem("token", response.data.token);
        }
        navigate(resolvePostLoginPath(searchParams.get("next")), { replace: true });
      } catch (err: unknown) {
        if (cancelled) return;
        if (handleTenantPortalAccessError(err)) {
          return;
        }
        const axiosErr = err as { response?: { data?: { error?: string } } };
        setError(axiosErr.response?.data?.error || t("an-error-occurred"));
      }
    }

    exchange();
    return () => {
      cancelled = true;
    };
  }, [navigate, searchParams, t]);

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
      <div
        className={`${panelBase} ${panelLeftLayout}`}
        style={{ background: AUTH_PANEL_LEFT_BACKGROUND }}
      />
      <div className={`${panelBase} ${panelRight}`}>
        <div className={AUTH_FORM_CARD_CLASS} style={AUTH_FORM_CARD_STYLE}>
          <Title order={2} ta="center" mb="md">
            {t("login")}
          </Title>
          {error ? (
            <Stack gap="md">
              <Alert color="red" variant="light">
                {error}
              </Alert>
              <Text ta="center" size="sm">
                <Anchor component={Link} to="/login">
                  {t("login")}
                </Anchor>
              </Text>
            </Stack>
          ) : (
            <Stack align="center" gap="md">
              <Loader color="violet" />
              <Text size="sm" c="dimmed">
                {t("successfully-logged-in")}
              </Text>
            </Stack>
          )}
        </div>
      </div>
    </div>
  );
}
