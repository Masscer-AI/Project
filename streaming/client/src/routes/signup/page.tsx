import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "react-hot-toast";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { API_URL } from "../../modules/constants";
import { useTranslation } from "react-i18next";
import {
  TextInput,
  PasswordInput,
  Button,
  Title,
  Text,
  Stack,
  Anchor,
  Loader,
  Divider,
  useMantineTheme,
} from "@mantine/core";
import { IconUserPlus, IconSparkles } from "@tabler/icons-react";
import { GoogleSignInButton } from "../../components/GoogleSignInButton/GoogleSignInButton";
import { hasGoogleOAuthClientId } from "../../modules/googleEnv";
import { redirectToTenantHandoff } from "../../utils/googleAuthHandoff";
import { resolvePostLoginPath } from "../../utils/loginRedirect";
import {
  buildTenantGoogleBridgeUrl,
  getCanonicalAppOrigin,
  isTenantSubdomainHost,
} from "../../utils/tenantSubdomain";
import {
  getPortalOriginPayload,
  handleTenantPortalAccessError,
} from "../../utils/tenantPortalAccess";
import {
  AUTH_FORM_CARD_CLASS,
  AUTH_FORM_CARD_STYLE,
  AUTH_INPUT_STYLES,
  AUTH_PANEL_LEFT_BACKGROUND,
  BRANDING_ICON_BOX_STYLE,
} from "../../utils/tenantTheme";

type Organization = {
  id: string;
  name: string;
  description?: string;
  logo_url?: string | null;
};

type InviteSignupGetResponse = {
  invite_valid: boolean;
  email_already_registered?: boolean;
  error?: string;
  organization?: Organization;
  email?: string;
  name?: string;
  bio?: string;
  expires_at?: string | null;
  invite_expires_at?: string;
};

const panelBase = "flex-1 flex flex-col justify-center items-center p-8";
const panelLeftLayout =
  "border-r border-white/[0.06] md:min-h-0 min-h-[40vh] md:border-b-0 border-b border-white/[0.06]";
const panelRight = "bg-[var(--bg-color,#0a0a0a)] md:min-h-0 min-h-[60vh]";
const brandingIconBoxClass =
  "w-[88px] h-[88px] mx-auto mb-6 rounded-2xl flex items-center justify-center";

export default function Signup() {
  const theme = useMantineTheme();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite");
  const orgId = searchParams.get("orgId");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [message, setMessage] = useState("");
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [inviteData, setInviteData] = useState<InviteSignupGetResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingOrg, setLoadingOrg] = useState(() => Boolean(inviteToken || orgId));

  const navigate = useNavigate();
  const { t } = useTranslation();

  // Invite token signup (email invitation) or orgId link or open signup
  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (inviteToken) {
        setLoadingOrg(true);
        try {
          const { data } = await axios.get<InviteSignupGetResponse>(
            `${API_URL}/v1/auth/signup?invite=${encodeURIComponent(inviteToken)}`
          );
          if (!cancelled) setInviteData(data);
        } catch {
          if (!cancelled) {
            setInviteData({
              invite_valid: false,
              error: "invalid-or-expired-invite",
            });
          }
        } finally {
          if (!cancelled) setLoadingOrg(false);
        }
        return;
      }

      if (orgId) {
        setLoadingOrg(true);
        try {
          const response = await axios.get<Organization>(
            `${API_URL}/v1/auth/signup?orgId=${orgId}`
          );
          if (!cancelled) setOrganization(response.data);
        } catch {
          if (!cancelled) setOrganization(null);
        } finally {
          if (!cancelled) setLoadingOrg(false);
        }
        return;
      }

      setInviteData(null);
      setOrganization(null);
      setLoadingOrg(false);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [inviteToken, orgId]);

  useEffect(() => {
    if (inviteData?.email) setEmail(inviteData.email);
  }, [inviteData?.email]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password.length < 8) {
      toast.error(t("password-min-length"));
      return;
    }
    if (password !== confirmPassword) {
      toast.error(t("passwords-do-not-match"));
      return;
    }

    // Email invitation — password only (email bound to invite)
    if (inviteToken && inviteData?.invite_valid) {
      setLoading(true);
      setMessage("");
      try {
        await axios.post(`${API_URL}/v1/auth/signup`, {
          invite_token: inviteToken,
          password,
          confirm_password: confirmPassword,
          ...getPortalOriginPayload(),
        });
        toast.success(t("user-created-succesfully-please-login"));
        navigate("/login");
      } catch (error: any) {
        if (handleTenantPortalAccessError(error)) {
          return;
        }
        const msg =
          error.response?.data?.error ||
          error.response?.data?.detail ||
          error.response?.data?.password?.[0] ||
          error.response?.data?.confirm_password?.[0] ||
          error.response?.data?.invite_token?.[0] ||
          error.response?.data?.non_field_errors?.[0] ||
          t("an-error-occurred");
        setMessage(typeof msg === "string" ? msg : t("an-error-occurred"));
        toast.error(typeof msg === "string" ? msg : t("an-error-occurred"));
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!orgId && !organizationName.trim()) {
      toast.error(t("organization-name-required"));
      return;
    }

    setLoading(true);
    setMessage("");

    const payload: Record<string, string> = {
      email,
      password,
      ...getPortalOriginPayload(),
    };
    if (orgId) {
      payload.organization_id = orgId;
    } else {
      payload.organization_name = organizationName.trim();
    }

    try {
      const response = await axios.post(API_URL + "/v1/auth/signup", payload);
      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success(t("user-created-succesfully-please-login"));
      navigate("/login");
    } catch (error: any) {
      if (handleTenantPortalAccessError(error)) {
        return;
      }
      const msg =
        error.response?.data?.detail ||
        error.response?.data?.email?.[0] ||
        error.response?.data?.error ||
        error.response?.data?.organization_id?.[0] ||
        error.response?.data?.organization_name?.[0] ||
        error.response?.data?.non_field_errors?.[0] ||
        t("an-error-occurred");
      setMessage(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleAccessToken = async (accessToken: string) => {
    if (inviteToken) return;
    setLoading(true);
    try {
      const returnTo = onTenantSubdomain
        ? window.location.origin
        : searchParams.get("return_to");
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
      navigate(resolvePostLoginPath(searchParams.get("next")));
    } catch (error: any) {
      if (handleTenantPortalAccessError(error)) {
        return;
      }
      const msg = error.response?.data?.error || t("an-error-occurred");
      setMessage(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const getInitialForLogo = (name: string) =>
    name.trim().slice(0, 2).toUpperCase() || "O";

  const isEmailInviteFlow = Boolean(inviteToken && inviteData?.invite_valid);
  const showGoogle = hasGoogleOAuthClientId && !inviteToken;
  const onTenantSubdomain = isTenantSubdomainHost();
  const googleAuthHref =
    showGoogle && onTenantSubdomain
      ? buildTenantGoogleBridgeUrl({
          returnTo: window.location.origin,
        })
      : undefined;

  if (onTenantSubdomain && !inviteToken && !orgId) {
    const mainAppSignup = `${getCanonicalAppOrigin()}/signup`;
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div
          className={`${panelBase} ${panelLeftLayout}`}
          style={{ background: AUTH_PANEL_LEFT_BACKGROUND }}
        />
        <div className={`${panelBase} ${panelRight}`}>
          <div className={AUTH_FORM_CARD_CLASS} style={AUTH_FORM_CARD_STYLE}>
            <Title order={2} ta="center" mb="md">
              {t("signup")}
            </Title>
            <Text ta="center" c="dimmed" mb="md">
              {t("tenant-portal-signup-forbidden")}
            </Text>
            <Stack gap="sm">
              <Text ta="center" size="sm">
                <Anchor component={Link} to="/login" c={theme.primaryColor}>
                  {t("switch-to-login")}
                </Anchor>
              </Text>
              <Text ta="center" size="sm">
                <Anchor href={mainAppSignup} c={theme.primaryColor}>
                  {t("tenant-portal-go-to-main-app")}
                </Anchor>
              </Text>
            </Stack>
          </div>
        </div>
      </div>
    );
  }

  // Loading invite or org details
  if (loadingOrg && (inviteToken || orgId)) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div
          className={`${panelBase} ${panelLeftLayout}`}
          style={{ background: AUTH_PANEL_LEFT_BACKGROUND }}
        >
          <Loader color={theme.primaryColor} />
        </div>
        <div className={`${panelBase} ${panelRight}`}>
          <div className={AUTH_FORM_CARD_CLASS} style={AUTH_FORM_CARD_STYLE}>
            <Title order={2} ta="center" mb="md">
              {t("signup")}
            </Title>
            <Text ta="center" c="dimmed">
              {t("loading")}...
            </Text>
          </div>
        </div>
      </div>
    );
  }

  // Invalid or expired email invite
  if (inviteToken && inviteData && !inviteData.invite_valid && !inviteData.email_already_registered) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div
          className={`${panelBase} ${panelLeftLayout}`}
          style={{ background: AUTH_PANEL_LEFT_BACKGROUND }}
        >
          <div className="text-center max-w-[360px]">
            <Title order={2} mb="sm">
              {t("signup")}
            </Title>
            <Text size="sm" c="dimmed">
              {t("invite-invalid-or-expired")}
            </Text>
          </div>
        </div>
        <div className={`${panelBase} ${panelRight}`}>
          <div className={AUTH_FORM_CARD_CLASS} style={AUTH_FORM_CARD_STYLE}>
            <Title order={2} ta="center" mb="md">
              {t("signup")}
            </Title>
            <Text ta="center" c="dimmed">
              {t("invite-invalid-or-expired")}
            </Text>
            <Text ta="center" mt="xl" size="sm">
              <Anchor component={Link} to="/login" c={theme.primaryColor}>
                {t("switch-to-login")}
              </Anchor>
            </Text>
          </div>
        </div>
      </div>
    );
  }

  // Email already registered for this invite
  if (inviteToken && inviteData?.email_already_registered) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div
          className={`${panelBase} ${panelLeftLayout}`}
          style={{ background: AUTH_PANEL_LEFT_BACKGROUND }}
        >
          <div className="text-center max-w-[360px]">
            <Title order={2} mb="sm">
              {t("signup")}
            </Title>
            <Text size="sm" c="dimmed">
              {t("invite-email-already-registered")}
            </Text>
          </div>
        </div>
        <div className={`${panelBase} ${panelRight}`}>
          <div className={AUTH_FORM_CARD_CLASS} style={AUTH_FORM_CARD_STYLE}>
            <Title order={2} ta="center" mb="md">
              {t("signup")}
            </Title>
            <Text ta="center" c="dimmed">
              {t("invite-email-already-registered")}
            </Text>
            <Text ta="center" mt="xl" size="sm">
              <Anchor component={Link} to="/login" c={theme.primaryColor}>
                {t("switch-to-login")}
              </Anchor>
            </Text>
          </div>
        </div>
      </div>
    );
  }

  // Org ID provided but org not found (generic link)
  if (orgId && !inviteToken && !organization) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div
          className={`${panelBase} ${panelLeftLayout}`}
          style={{ background: AUTH_PANEL_LEFT_BACKGROUND }}
        >
          <div className="text-center max-w-[360px]">
            <Title order={2} mb="sm">
              {t("signup")}
            </Title>
            <Text size="sm" c="dimmed">
              {t("organization-not-found")}
            </Text>
            <Text size="sm" c="dimmed">
              {t("use-valid-signup-link")}
            </Text>
          </div>
        </div>
        <div className={`${panelBase} ${panelRight}`}>
          <div className={AUTH_FORM_CARD_CLASS} style={AUTH_FORM_CARD_STYLE}>
            <Title order={2} ta="center" mb="md">
              {t("signup")}
            </Title>
            <Text ta="center" c="dimmed">
              {t("organization-not-found")}
            </Text>
            <Text ta="center" mt="xl" size="sm">
              <Anchor component={Link} to="/login" c={theme.primaryColor}>
                {t("switch-to-login")}
              </Anchor>
            </Text>
          </div>
        </div>
      </div>
    );
  }

  const inviteOrg = inviteData?.organization;
  const isInvitedOrgLink = !!orgId && !!organization && !inviteToken;
  const leftOrg = isEmailInviteFlow ? inviteOrg : organization;

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
      {/* Left panel */}
      <div
        className={`${panelBase} ${panelLeftLayout}`}
        style={{ background: AUTH_PANEL_LEFT_BACKGROUND }}
      >
        <div className="text-center max-w-[380px]">
          {isEmailInviteFlow && leftOrg ? (
            <>
              {leftOrg.logo_url ? (
                <img
                  src={`${API_URL}${leftOrg.logo_url}`}
                  alt={leftOrg.name}
                  className="block w-[88px] h-[88px] mx-auto mb-6 rounded-2xl object-cover border border-white/10 bg-white/5"
                />
              ) : (
                <div
                  className={`${brandingIconBoxClass} text-3xl font-semibold text-white/90 uppercase`}
                  style={BRANDING_ICON_BOX_STYLE}
                >
                  {getInitialForLogo(leftOrg.name)}
                </div>
              )}
              <Text
                size="xs"
                c="dimmed"
                className="uppercase tracking-wider"
                mb="xs"
              >
                {t("joining")}
              </Text>
              <Title order={1} className="!text-[1.75rem] !font-semibold !mb-3">
                {leftOrg.name}
              </Title>
              {leftOrg.description && (
                <Text size="sm" c="dimmed" className="leading-relaxed">
                  {leftOrg.description}
                </Text>
              )}
            </>
          ) : isInvitedOrgLink ? (
            <>
              {organization?.logo_url ? (
                <img
                  src={`${API_URL}${organization.logo_url}`}
                  alt={organization.name}
                  className="block w-[88px] h-[88px] mx-auto mb-6 rounded-2xl object-cover border border-white/10 bg-white/5"
                />
              ) : (
                <div
                  className={`${brandingIconBoxClass} text-3xl font-semibold text-white/90 uppercase`}
                  style={BRANDING_ICON_BOX_STYLE}
                >
                  {organization ? getInitialForLogo(organization.name) : "O"}
                </div>
              )}
              <Text
                size="xs"
                c="dimmed"
                className="uppercase tracking-wider"
                mb="xs"
              >
                {t("joining")}
              </Text>
              <Title order={1} className="!text-[1.75rem] !font-semibold !mb-3">
                {organization?.name ?? ""}
              </Title>
              {organization?.description && (
                <Text size="sm" c="dimmed" className="leading-relaxed">
                  {organization.description}
                </Text>
              )}
            </>
          ) : (
            <>
              <div className={brandingIconBoxClass} style={BRANDING_ICON_BOX_STYLE}>
                <IconSparkles size={40} className="text-white/90" />
              </div>
              <Title order={1} className="!text-[1.75rem] !font-semibold !mb-3">
                {t("create-your-account")}
              </Title>
              <Text size="sm" c="dimmed" className="leading-relaxed">
                {t("signup-open-description")}
              </Text>
            </>
          )}
        </div>
      </div>

      {/* Right panel — form */}
      <div className={`${panelBase} ${panelRight}`}>
        <div className={AUTH_FORM_CARD_CLASS} style={AUTH_FORM_CARD_STYLE}>
          <Title order={2} ta="center" mb="xl">
            {isEmailInviteFlow ? t("signup-invite-set-password") : t("signup")}
          </Title>

          {showGoogle && (
            <>
              <GoogleSignInButton
                onAccessToken={googleAuthHref ? undefined : handleGoogleAccessToken}
                href={googleAuthHref}
                disabled={loading}
              />
              <Divider label="or" labelPosition="center" my="lg" />
            </>
          )}

          <form onSubmit={handleSubmit}>
            <Stack gap="md">
              <TextInput
                label={t("email")}
                placeholder={t("email")}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
                required
                readOnly={isEmailInviteFlow}
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
                required
                name="password"
                autoComplete="new-password"
                variant="filled"
                size="md"
                styles={AUTH_INPUT_STYLES}
                error={
                  password.length > 0 && password.length < 8
                    ? t("password-min-length")
                    : undefined
                }
              />
              <PasswordInput
                label={t("confirm-password")}
                placeholder={t("confirm-password")}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.currentTarget.value)}
                required
                name="confirm-password"
                autoComplete="new-password"
                variant="filled"
                size="md"
                styles={AUTH_INPUT_STYLES}
                error={
                  confirmPassword.length > 0 && password !== confirmPassword
                    ? t("passwords-do-not-match")
                    : undefined
                }
              />

              {!isEmailInviteFlow && !isInvitedOrgLink && (
                <TextInput
                  label={t("organization-name")}
                  placeholder={t("organization-name")}
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.currentTarget.value)}
                  required
                  name="organization_name"
                  variant="filled"
                  size="md"
                  styles={AUTH_INPUT_STYLES}
                />
              )}

              {message && (
                <Text size="sm" c="red" ta="center">
                  {message}
                </Text>
              )}

              <Button
                type="submit"
                loading={loading}
                fullWidth
                size="md"
                mt="xs"
                leftSection={!loading ? <IconUserPlus size={18} /> : undefined}
              >
                {isEmailInviteFlow ? t("signup-invite-submit") : t("signup")}
              </Button>
            </Stack>
          </form>

          <Text ta="center" mt="xl" size="sm">
            <Anchor component={Link} to="/login" c={theme.primaryColor}>
              {t("switch-to-login")}
            </Anchor>
          </Text>
        </div>
      </div>
    </div>
  );
}
