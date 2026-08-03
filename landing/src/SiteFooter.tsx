import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Brand } from "./Brand";
import { LanguageSwitcher } from "./LanguageSwitcher";

export function SiteFooter() {
  const { t } = useTranslation();

  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <p className="site-footer__brand">
          <Brand />
        </p>
        <nav className="site-footer__nav" aria-label={t("footer-legal-aria")}>
          <Link to="/about">{t("footer-about")}</Link>
          <Link to="/privacy">{t("footer-privacy")}</Link>
          <Link to="/terms">{t("footer-terms")}</Link>
          <a href="mailto:masscer.ai@gmail.com">{t("footer-contact")}</a>
          <LanguageSwitcher />
        </nav>
      </div>
    </footer>
  );
}
