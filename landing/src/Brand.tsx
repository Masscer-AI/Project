import { useTranslation } from "react-i18next";

export function Brand({ className }: { className?: string }) {
  const { t } = useTranslation();
  return <span className={className}>{t("brand")}</span>;
}
