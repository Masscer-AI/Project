import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Brand } from "./Brand";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { SiteFooter } from "./SiteFooter";

const APP_URL = "https://app.masscer.ai";

const FEATURE_KEYS = [
  { title: "feature-agents-title", desc: "feature-agents-desc" },
  { title: "feature-whatsapp-title", desc: "feature-whatsapp-desc" },
  { title: "feature-embed-title", desc: "feature-embed-desc" },
  { title: "feature-relationships-title", desc: "feature-relationships-desc" },
] as const;

export function HomePage() {
  const { t } = useTranslation();

  return (
    <div className="page">
      <div className="atmosphere" aria-hidden="true" />

      <header className="topbar">
        <a className="logo" href="/">
          <Brand />
        </a>
        <nav className="topbar__nav">
          <LanguageSwitcher />
          <Link className="topbar__link" to="/about">
            {t("nav-about")}
          </Link>
          <Link className="topbar__link" to="/privacy">
            {t("nav-privacy")}
          </Link>
          <a className="btn btn--ghost topbar__login" href={`${APP_URL}/login`}>
            {t("nav-login")}
          </a>
          <a className="btn btn--primary" href={`${APP_URL}/signup`}>
            {t("nav-get-started")}
          </a>
        </nav>
      </header>

      <main>
        <section className="hero">
          <p className="hero__brand">
            <Brand />
          </p>
          <h1 className="hero__headline">{t("hero-headline")}</h1>
          <p className="hero__lede">{t("hero-lede")}</p>
          <div className="hero__cta">
            <a className="btn btn--primary btn--lg" href={`${APP_URL}/signup`}>
              {t("nav-get-started")}
            </a>
            <a className="btn btn--ghost btn--lg" href={`${APP_URL}/login`}>
              {t("nav-open-app")}
            </a>
          </div>
          <p className="hero__note">{t("hero-no-card")}</p>
        </section>

        <section className="purpose" aria-labelledby="purpose-title">
          <h2 id="purpose-title" className="purpose__title">
            {t("purpose-title")}
          </h2>
          <p className="purpose__body">{t("purpose-body")}</p>
          <div className="purpose__grid">
            <article className="purpose__card">
              <h3>{t("purpose-who")}</h3>
              <p>{t("purpose-who-body")}</p>
            </article>
            <article className="purpose__card">
              <h3>{t("purpose-how")}</h3>
              <p>{t("purpose-how-body")}</p>
            </article>
          </div>
        </section>

        <section className="features" aria-labelledby="features-title">
          <h2 id="features-title" className="features__title">
            {t("features-title")}
          </h2>
          <ul className="features__grid">
            {FEATURE_KEYS.map((f) => (
              <li key={f.title} className="feature">
                <h3>{t(f.title)}</h3>
                <p>{t(f.desc)}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="mission" aria-labelledby="mission-heading">
          <h2 id="mission-heading" className="mission__heading">
            {t("nav-about")}
          </h2>
          <div className="mission__grid">
            <article className="mission__card">
              <h3>{t("mission-title")}</h3>
              <p>{t("mission-body")}</p>
            </article>
            <article className="mission__card">
              <h3>{t("vision-title")}</h3>
              <p>{t("vision-body")}</p>
            </article>
          </div>
          <p className="mission__more">
            <Link to="/about">{t("footer-about")} →</Link>
          </p>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
