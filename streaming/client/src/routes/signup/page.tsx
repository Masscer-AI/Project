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
} from "@mantine/core";
import { IconUserPlus, IconSparkles } from "@tabler/icons-react";

type Organization = {
  id: string;
  name: string;
  description?: string;
  logo_url?: string | null;
};

const panelBase = "flex-1 flex flex-col justify-center items-center p-8";
const panelLeft =
  "bg-[radial-gradient(ellipse_80%_60%_at_30%_50%,rgba(110,91,255,0.15),transparent),linear-gradient(180deg,rgba(20,20,25,0.98)_0%,rgba(15,15,20,0.99)_100%)] border-r border-white/[0.06] md:min-h-0 min-h-[40vh] md:border-b-0 border-b border-white/[0.06]";
const panelRight = "bg-[var(--bg-color,#0a0a0a)] md:min-h-0 min-h-[60vh]";
const formCard =
  "w-full max-w-[400px] p-10 rounded-2xl border border-white/[0.08] shadow-2xl bg-[var(--modal-bg-color,rgba(28,28,32,0.98))]";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [message, setMessage] = useState("");
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingOrg, setLoadingOrg] = useState(false);

  const [searchParams] = useSearchParams();
  const orgId = searchParams.get("orgId");

  const navigate = useNavigate();
  const { t } = useTranslation();

  // If orgId is in the URL, fetch organization details
  useEffect(() => {
    if (!orgId) return;

    setLoadingOrg(true);
    const fetchOrganization = async () => {
      try {
        const response = await axios.get<Organization>(
          `${API_URL}/v1/auth/signup?orgId=${orgId}`
        );
        setOrganization(response.data);
      } catch {
        setOrganization(null);
      } finally {
        setLoadingOrg(false);
      }
    };

    fetchOrganization();
  }, [orgId]);

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
    if (!orgId && !organizationName.trim()) {
      toast.error(t("organization-name-required"));
      return;
    }

    setLoading(true);
    setMessage("");

    const payload: Record<string, string> = { username, email, password };
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

  const getInitialForLogo = (name: string) =>
    name.trim().slice(0, 2).toUpperCase() || "O";

  // Loading org details
  if (loadingOrg) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div className={`${panelBase} ${panelLeft}`}>
          <Loader color="violet" />
        </div>
        <div className={`${panelBase} ${panelRight}`}>
          <div className={formCard}>
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

  // Org ID provided but org not found
  if (orgId && !loadingOrg && !organization) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div className={`${panelBase} ${panelLeft}`}>
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
          <div className={formCard}>
            <Title order={2} ta="center" mb="md">
              {t("signup")}
            </Title>
            <Text ta="center" c="dimmed">
              {t("organization-not-found")}
            </Text>
            <Text ta="center" mt="xl" size="sm">
              <Anchor component={Link} to="/login" c="violet">
                {t("switch-to-login")}
              </Anchor>
            </Text>
          </div>
        </div>
      </div>
    );
  }

  // Invited signup (has org) or open signup (no org)
  const isInvited = !!orgId && !!organization;

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
      {/* Left panel */}
      <div className={`${panelBase} ${panelLeft}`}>
        <div className="text-center max-w-[380px]">
          {isInvited ? (
            <>
              {organization?.logo_url ? (
                <img
                  src={`${API_URL}${organization.logo_url}`}
                  alt={organization.name}
                  className="block w-[88px] h-[88px] mx-auto mb-6 rounded-2xl object-cover border border-white/10 bg-white/5"
                />
              ) : (
                <div className="w-[88px] h-[88px] mx-auto mb-6 rounded-2xl flex items-center justify-center bg-[rgba(110,91,255,0.2)] border border-[rgba(110,91,255,0.3)] text-3xl font-semibold text-white/90 uppercase">
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
              <div className="w-[88px] h-[88px] mx-auto mb-6 rounded-2xl flex items-center justify-center bg-[rgba(110,91,255,0.2)] border border-[rgba(110,91,255,0.3)]">
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
        <div className={formCard}>
          <Title order={2} ta="center" mb="xl">
            {t("signup")}
          </Title>

          <form onSubmit={handleSubmit}>
            <Stack gap="md">
              <TextInput
                label={t("username")}
                placeholder={t("username")}
                value={username}
                onChange={(e) => setUsername(e.currentTarget.value)}
                required
                name="username"
                autoComplete="username"
                variant="filled"
                size="md"
              />
              <TextInput
                label={t("email")}
                placeholder={t("email")}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
                required
                name="email"
                autoComplete="email"
                variant="filled"
                size="md"
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
                error={
                  confirmPassword.length > 0 && password !== confirmPassword
                    ? t("passwords-do-not-match")
                    : undefined
                }
              />

              {!isInvited && (
                <TextInput
                  label={t("organization-name")}
                  placeholder={t("organization-name")}
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.currentTarget.value)}
                  required
                  name="organization_name"
                  variant="filled"
                  size="md"
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
                {t("signup")}
              </Button>
            </Stack>
          </form>

          <Text ta="center" mt="xl" size="sm">
            <Anchor component={Link} to="/login" c="violet">
              {t("switch-to-login")}
            </Anchor>
          </Text>
        </div>
      </div>
    </div>
  );
}
