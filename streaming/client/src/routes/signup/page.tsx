import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "react-hot-toast";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { API_URL, DEFAULT_ORGANIZATION_ID } from "../../modules/constants";
import { useTranslation } from "react-i18next";

type Organization = {
  id: string;
  name: string;
  description?: string;
  logo_url?: string | null;
};

const panelBase =
  "flex-1 flex flex-col justify-center items-center p-8";
const panelLeft =
  "bg-[radial-gradient(ellipse_80%_60%_at_30%_50%,rgba(110,91,255,0.15),transparent),linear-gradient(180deg,rgba(20,20,25,0.98)_0%,rgba(15,15,20,0.99)_100%)] border-r border-white/[0.06] md:min-h-0 min-h-[40vh] md:border-b-0 border-b border-white/[0.06]";
const panelRight = "bg-[var(--bg-color,#0a0a0a)] md:min-h-0 min-h-[60vh]";
const formCard =
  "w-full max-w-[400px] p-10 rounded-2xl border border-white/[0.08] shadow-2xl bg-[var(--modal-bg-color,rgba(28,28,32,0.98))]";
const formTitle = "text-2xl font-semibold mb-7 text-center text-[var(--font-color,#fff)]";
const formGroup = "mb-5";
const inputClass =
  "w-full px-3.5 py-3 rounded-xl border border-white/20 bg-white/5 text-[var(--font-color,#fff)] text-base placeholder:text-white/35 focus:outline-none focus:border-[rgba(110,91,255,0.6)] focus:ring-2 focus:ring-[rgba(110,91,255,0.15)] disabled:opacity-60 disabled:cursor-not-allowed transition-colors";
const labelClass = "block text-sm text-white/60 mb-1.5";
const submitBtn =
  "w-full mt-2 py-3.5 px-5 rounded-xl border-0 text-base font-semibold cursor-pointer transition-all bg-gradient-to-br from-[#6e5bff] to-[#5a47e6] text-white hover:enabled:from-[#7d6bff] hover:enabled:to-[#6b56f0] active:enabled:scale-[0.99] disabled:opacity-60 disabled:cursor-not-allowed";
const linkLogin =
  "block text-center mt-6 text-sm text-[rgba(110,91,255,0.9)] no-underline hover:text-[rgba(140,120,255,1)] transition-colors";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingOrg, setLoadingOrg] = useState(true);

  const [searchParams] = useSearchParams();
  const orgId = searchParams.get("orgId");

  const navigate = useNavigate();
  const { t } = useTranslation();

  useEffect(() => {
    if (!orgId) {
      if (DEFAULT_ORGANIZATION_ID) {
        navigate(`/signup?orgId=${DEFAULT_ORGANIZATION_ID}`, { replace: true });
        return;
      }
      setLoadingOrg(false);
      return;
    }

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
  }, [orgId, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!orgId) {
      setMessage("Organization ID is required");
      return;
    }

    setLoading(true);
    const endpoint = "/v1/auth/signup";
    const payload = { username, email, password, organization_id: orgId };
    try {
      const response = await axios.post(API_URL + endpoint, payload);
      setMessage(response.data.message);
      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success(t("user-created-succesfully-please-login"));
      navigate("/login");
    } catch (error: any) {
      setMessage(
        error.response?.data?.detail ||
          error.response?.data?.email ||
          error.response?.data?.error ||
          error.response?.data?.organization_id?.[0] ||
          "An error occurred"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (message && orgId) {
      toast.error(message);
    }
  }, [message, orgId]);

  const getInitialForLogo = (name: string) =>
    name.trim().slice(0, 2).toUpperCase() || "O";

  const errorOrLoadingContent = (
    <div className="text-center max-w-[360px]">
      <h2 className="text-xl mb-3 text-[var(--font-color,#fff)]">{t("signup")}</h2>
      <p className="text-[0.95rem] text-white/60 leading-relaxed m-0">{t("loading")}...</p>
    </div>
  );

  if (loadingOrg) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div className={`${panelBase} ${panelLeft}`}>{errorOrLoadingContent}</div>
        <div className={`${panelBase} ${panelRight}`}>
          <div className={formCard}>
            <h2 className={formTitle}>{t("signup")}</h2>
            <p className="text-center text-white/50">{t("loading")}...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!orgId) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div className={`${panelBase} ${panelLeft}`}>
          <div className="text-center max-w-[360px]">
            <h2 className="text-xl mb-3 text-[var(--font-color,#fff)]">{t("signup")}</h2>
            <p className="text-[0.95rem] text-white/60 leading-relaxed m-0">{t("organization-id-required")}</p>
            <p className="text-[0.95rem] text-white/60 leading-relaxed m-0">{t("use-valid-signup-link")}</p>
          </div>
        </div>
        <div className={`${panelBase} ${panelRight}`}>
          <div className={formCard}>
            <h2 className={formTitle}>{t("signup")}</h2>
            <p className="text-center text-white/60">{t("organization-id-required")}</p>
            <Link to="/login" className={linkLogin}>{t("switch-to-login")}</Link>
          </div>
        </div>
      </div>
    );
  }

  if (!loadingOrg && !organization && orgId) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
        <div className={`${panelBase} ${panelLeft}`}>
          <div className="text-center max-w-[360px]">
            <h2 className="text-xl mb-3 text-[var(--font-color,#fff)]">{t("signup")}</h2>
            <p className="text-[0.95rem] text-white/60 leading-relaxed m-0">{t("organization-not-found")}</p>
            <p className="text-[0.95rem] text-white/60 leading-relaxed m-0">{t("use-valid-signup-link")}</p>
          </div>
        </div>
        <div className={`${panelBase} ${panelRight}`}>
          <div className={formCard}>
            <h2 className={formTitle}>{t("signup")}</h2>
            <p className="text-center text-white/60">{t("organization-not-found")}</p>
            <Link to="/login" className={linkLogin}>{t("switch-to-login")}</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
      <div className={`${panelBase} ${panelLeft}`}>
        <div className="text-center max-w-[380px]">
          {organization?.logo_url ? (
            <img
              src={organization.logo_url}
              alt={organization.name}
              className="block w-[88px] h-[88px] mx-auto mb-6 rounded-2xl object-cover border border-white/10 bg-white/5"
            />
          ) : (
            <div className="w-[88px] h-[88px] mx-auto mb-6 rounded-2xl flex items-center justify-center bg-[rgba(110,91,255,0.2)] border border-[rgba(110,91,255,0.3)] text-3xl font-semibold text-white/90 uppercase">
              {organization ? getInitialForLogo(organization.name) : "O"}
            </div>
          )}
          <p className="text-[0.85rem] text-white/50 mb-2 uppercase tracking-wider">{t("joining")}</p>
          <h1 className="text-[1.75rem] font-semibold m-0 mb-3 text-[var(--font-color,#fff)]">
            {organization?.name ?? ""}
          </h1>
          {organization?.description && (
            <p className="text-[0.95rem] text-white/65 leading-normal m-0">
              {organization.description}
            </p>
          )}
        </div>
      </div>

      <div className={`${panelBase} ${panelRight}`}>
        <div className={formCard}>
          <h2 className={formTitle}>{t("signup")}</h2>

          <form onSubmit={handleSubmit}>
            <div className={formGroup}>
              <label htmlFor="username" className={labelClass}>{t("username")}</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                name="username"
                autoComplete="username"
                placeholder={t("username")}
                disabled={!orgId}
                className={inputClass}
              />
            </div>
            <div className={formGroup}>
              <label htmlFor="email" className={labelClass}>{t("email")}</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                name="email"
                autoComplete="email"
                placeholder={t("email")}
                disabled={!orgId}
                className={inputClass}
              />
            </div>
            <div className={formGroup}>
              <label htmlFor="password" className={labelClass}>{t("password")}</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                name="password"
                autoComplete="new-password"
                placeholder={t("password")}
                disabled={!orgId}
                className={inputClass}
              />
            </div>
            <button
              type="submit"
              className={submitBtn}
              disabled={loading || !orgId}
            >
              {loading ? t("loading") : t("signup")}
            </button>
          </form>

          <Link to="/login" className={linkLogin}>
            {t("switch-to-login")}
          </Link>
        </div>
      </div>
    </div>
  );
}
