import { useTranslation } from "react-i18next";
import { setLanguage, type Lang } from "./i18n";

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const current = (i18n.language?.split("-")[0] ?? "en") as Lang;

  return (
    <div className="lang-switch" role="group" aria-label={t("lang-aria")}>
      {(["en", "es"] as const).map((lang) => (
        <button
          key={lang}
          type="button"
          className={`lang-switch__btn${current === lang ? " is-active" : ""}`}
          onClick={() => setLanguage(lang)}
          aria-pressed={current === lang}
        >
          {t(`lang-${lang}`)}
        </button>
      ))}
    </div>
  );
}
