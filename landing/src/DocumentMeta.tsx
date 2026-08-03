import { useEffect } from "react";
import { useTranslation } from "react-i18next";

/** Keep <title> and meta description in sync with the active language. */
export function DocumentMeta() {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    document.title = t("meta-title");
    const meta = document.querySelector('meta[name="description"]');
    if (meta) {
      meta.setAttribute("content", t("meta-description"));
    }
  }, [t, i18n.language]);

  return null;
}
