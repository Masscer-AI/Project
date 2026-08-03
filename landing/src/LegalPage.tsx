import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Markdown } from "./markdown";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { SiteFooter } from "./SiteFooter";
import privacyEn from "./content/privacy.en.md?raw";
import privacyEs from "./content/privacy.es.md?raw";
import termsEn from "./content/terms.en.md?raw";
import termsEs from "./content/terms.es.md?raw";

type DocId = "privacy" | "terms";
type Lang = "en" | "es";

const DOCS: Record<DocId, Record<Lang, string>> = {
  privacy: { en: privacyEn, es: privacyEs },
  terms: { en: termsEn, es: termsEs },
};

const TITLE_KEYS: Record<DocId, string> = {
  privacy: "legal-privacy-title",
  terms: "legal-terms-title",
};

export function LegalPage({ docId }: { docId: DocId }) {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language?.split("-")[0] === "es" ? "es" : "en") as Lang;
  const source = DOCS[docId][lang];

  return (
    <div className="page page--legal">
      <div className="atmosphere atmosphere--subtle" aria-hidden="true" />

      <header className="topbar">
        <Link className="logo" to="/">
          Masscer
        </Link>
        <nav className="topbar__nav">
          <LanguageSwitcher />
          <Link className="topbar__link" to="/privacy">
            {t("nav-privacy")}
          </Link>
          <Link className="topbar__link" to="/terms">
            {t("nav-terms")}
          </Link>
          <a className="btn btn--primary" href="https://app.masscer.ai/signup">
            {t("nav-get-started")}
          </a>
        </nav>
      </header>

      <main className="legal">
        <p className="legal__back">
          <Link to="/">{t("legal-back")}</Link>
        </p>
        <h1>{t(TITLE_KEYS[docId])}</h1>
        <Markdown source={source} />
      </main>

      <SiteFooter />
    </div>
  );
}
