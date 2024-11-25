import React from "react";
import { useTranslation } from "react-i18next";

export const ErrorPage = () => {
  const { t } = useTranslation();

  return (
    <div >
      <h1>{t("sorry-an-unexpected-error-happen")}</h1>
      <p>{t("notify-developers")}</p>
    </div>
  );
};
