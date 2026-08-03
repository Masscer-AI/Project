import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Brand } from "./Brand";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { SiteFooter } from "./SiteFooter";

const APP_URL = "https://app.masscer.ai";

export function AboutPage() {
  const { t } = useTranslation();

  return (
    <div className="page page--legal">
      <div className="atmosphere atmosphere--subtle" aria-hidden="true" />

      <header className="topbar">
        <Link className="logo" to="/">
          <Brand />
        </Link>
        <nav className="topbar__nav">
          <LanguageSwitcher />
          <Link className="topbar__link" to="/about">
            {t("nav-about")}
          </Link>
          <Link className="topbar__link" to="/privacy">
            {t("nav-privacy")}
          </Link>
          <a className="btn btn--primary" href={`${APP_URL}/signup`}>
            {t("nav-get-started")}
          </a>
        </nav>
      </header>

      <main className="legal about">
        <p className="legal__back">
          <Link to="/">{t("legal-back")}</Link>
        </p>
        <h1>{t("about-page-title")}</h1>
        <p className="about__intro">{t("about-page-intro")}</p>

        <section className="about__block" aria-labelledby="about-purpose">
          <h2 id="about-purpose">{t("about-purpose-title")}</h2>
          <p>{t("about-purpose-body")}</p>
        </section>

        <section className="about__block" aria-labelledby="about-mission">
          <h2 id="about-mission">{t("mission-title")}</h2>
          <p>{t("mission-body")}</p>
        </section>

        <section className="about__block" aria-labelledby="about-vision">
          <h2 id="about-vision">{t("vision-title")}</h2>
          <p>{t("vision-body")}</p>
        </section>

        <div className="about__cta">
          <a className="btn btn--primary" href={`${APP_URL}/signup`}>
            {t("nav-get-started")}
          </a>
          <Link className="btn btn--ghost" to="/privacy">
            {t("nav-privacy")}
          </Link>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
