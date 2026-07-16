import React from "react";
import i18n from "../../i18next";

export const ErrorPage = () => {
  return (
    <div>
      <h1>{i18n.t("sorry-an-unexpected-error-happen")}</h1>
      <p>{i18n.t("notify-developers")}</p>
    </div>
  );
};
