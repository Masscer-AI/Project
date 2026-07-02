import React, { useState } from "react";
import axios from "axios";
import { toast } from "react-hot-toast";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { API_URL } from "../../modules/constants";
import { resolvePostLoginPath } from "../../utils/loginRedirect";
import { useTranslation } from "react-i18next";
import {
  Alert,
  TextInput,
  PasswordInput,
  Button,
  Title,
  Text,
  Stack,
  Anchor,
  Divider,
  useMantineTheme,
} from "@mantine/core";
import { IconLogin, IconLock, IconSparkles } from "@tabler/icons-react";
import { GoogleSignInButton } from "../../components/GoogleSignInButton/GoogleSignInButton";
import { hasGoogleOAuthClientId } from "../../modules/googleEnv";
import {
  buildTenantGoogleBridgeUrl,
  isTenantSubdomainHost,
} from "../../utils/tenantSubdomain";
import {
  redirectToTenantHandoff,
} from "../../utils/googleAuthHandoff";
import {
  AUTH_FORM_CARD_CLASS,
  AUTH_FORM_CARD_STYLE,
  AUTH_INPUT_STYLES,
  AUTH_PANEL_LEFT_BACKGROUND,
  BRANDING_ICON_BOX_STYLE,
} from "../../utils/tenantTheme";

const panelBase = "flex-1 flex flex-col justify-center items-center p-8";
const panelLeftLayout =
  "border-r border-white/[0.06] md:min-h-0 min-h-[40vh] md:border-b-0 border-b border-white/[0.06]";
const panelRight = "bg-[var(--bg-color,#0a0a0a)] md:min-h-0 min-h-[60vh]";
const brandingIconBoxClass =
  "w-[88px] h-[88px] mx-auto mb-6 rounded-2xl flex items-center justify-center";

export default function Login() {
  const theme = useMantineTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isDeactivated, setIsDeactivated] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();

  const redirectAfterLogin = () => {
    navigate(resolvePostLoginPath(searchParams.get("next")));
  };

  const onTenantSubdomain = isTenantSubdomainHost();
  const googleAuthHref = onTenantSubdomain
    ? buildTenantGoogleBridgeUrl({
        returnTo: window.location.origin,
        next: searchParams.get("next"),
      })
    : undefined;

  const handleSubmit = async () => {
    if (!email || !password) {
      toast.error(t("email-and-password-required"));
      return;
    }

    setIsLoading(true);
    setErrorMessage("");
    setIsDeactivated(false);
    try {
      const response = await axios.post(API_URL + "/v1/auth/login", {
        email,
        password,
      });
      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success(t("successfully-logged-in"));
      redirectAfterLogin();
    } catch (error: any) {
      console.error("LOGIN ERROR: ", error);
      const status = error.response?.status;
      const serverMsg =
        error.response?.data?.error ||
        error.response?.data?.detail;

      if (status === 403) {
        setIsDeactivated(true);
        setErrorMessage(t("account-deactivated"));
      } else if (error.code === "ERR_NETWORK") {
        const msg = t("network-error");
        setErrorMessage(msg);
        toast.error(msg);
      } else if (status === 401) {
        const msg = t("invalid-credentials");
        setErrorMessage(msg);
      } else {
        const msg = t("an-error-occurred");
        setErrorMessage(msg);
        toast.error(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSubmit();
    }
  };

  const handleGoogleAccessToken = async (accessToken: string) => {
    setIsLoading(true);
    try {
      const returnTo = searchParams.get("return_to");
      const response = await axios.post(API_URL + "/v1/auth/google", {
        access_token: accessToken,
        ...(returnTo ? { return_to: returnTo } : {}),
      });

      if (returnTo && response.data.handoff_code) {
        redirectToTenantHandoff(
          response.data.handoff_code,
          returnTo,
          searchParams.get("next")
        );
        return;
      }

      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success(t("successfully-logged-in"));
      redirectAfterLogin();
    } catch (error: any) {
      const msg = error.response?.data?.error || t("an-error-occurred");
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
      {/* Left panel — branding */}
      <div
        className={`${panelBase} ${panelLeftLayout}`}
        style={{ background: AUTH_PANEL_LEFT_BACKGROUND }}
      >
        <div className="text-center max-w-[380px]">
          <div className={brandingIconBoxClass} style={BRANDING_ICON_BOX_STYLE}>
            <IconSparkles size={40} className="text-white/90" />
          </div>
          <Title order={1} className="!text-[1.75rem] !font-semibold !mb-3">
            {t("welcome-back")}
          </Title>
          <Text size="sm" c="dimmed" className="leading-relaxed">
            {t("login-description")}
          </Text>
        </div>
      </div>

      {/* Right panel — form */}
      <div className={`${panelBase} ${panelRight}`}>
        <div className={AUTH_FORM_CARD_CLASS} style={AUTH_FORM_CARD_STYLE}>
          <Title order={2} ta="center" mb="xl">
            {t("login")}
          </Title>

          <form onSubmit={(e) => e.preventDefault()}>
            <Stack gap="md">
              <TextInput
                label={t("email")}
                placeholder={t("email")}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
                onKeyDown={handleKeyDown}
                required
                name="email"
                autoComplete="email"
                variant="filled"
                size="md"
                styles={AUTH_INPUT_STYLES}
              />
              <PasswordInput
                label={t("password")}
                placeholder={t("password")}
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                onKeyDown={handleKeyDown}
                required
                name="password"
                autoComplete="current-password"
                variant="filled"
                size="md"
                styles={AUTH_INPUT_STYLES}
              />
              <Anchor
                component={Link}
                to="/forgot-password"
                c={theme.primaryColor}
                size="sm"
                ta="right"
              >
                {t("forgot-password")}
              </Anchor>

              {isDeactivated && (
                <Alert
                  variant="light"
                  color="yellow"
                  title={t("account-deactivated-title")}
                  icon={<IconLock size={18} />}
                >
                  {t("account-deactivated-description")}
                </Alert>
              )}

              {errorMessage && !isDeactivated && (
                <Text size="sm" c="red" ta="center">
                  {errorMessage}
                </Text>
              )}

              <Button
                onClick={handleSubmit}
                loading={isLoading}
                fullWidth
                size="md"
                mt="xs"
                leftSection={!isLoading ? <IconLogin size={18} /> : undefined}
              >
                {t("login")}
              </Button>
            </Stack>
          </form>

          {hasGoogleOAuthClientId && (
            <>
              <Divider label="or" labelPosition="center" my="lg" />
              <GoogleSignInButton
                onAccessToken={googleAuthHref ? undefined : handleGoogleAccessToken}
                href={googleAuthHref}
                disabled={isLoading}
              />
            </>
          )}

          <Text ta="center" mt="xl" size="sm">
            <Anchor component={Link} to="/signup" c={theme.primaryColor}>
              {t("go-to-signup")}
            </Anchor>
          </Text>
        </div>
      </div>
    </div>
  );
}
