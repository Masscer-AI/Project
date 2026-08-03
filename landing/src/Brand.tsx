import { useTranslation } from "react-i18next";

/** App name must match Google OAuth consent screen: MasscerAI */
export function Brand({ className }: { className?: string }) {
  const { t } = useTranslation();
  return <span className={className}>{t("brand")}</span>;
}
