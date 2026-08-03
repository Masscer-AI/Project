import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "./LanguageSwitcher";

export function SiteFooter() {
  const { t } = useTranslation();

  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <p className="site-footer__brand">Masscer</p>
        <nav className="site-footer__nav" aria-label={t("footer-legal-aria")}>
          <Link to="/privacy">{t("footer-privacy")}</Link>
          <Link to="/terms">{t("footer-terms")}</Link>
          <a href="mailto:masscer.ai@gmail.com">{t("footer-contact")}</a>
          <LanguageSwitcher />
        </nav>
      </div>
    </footer>
  );
}
