import React from "react";

import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { useTranslation } from "react-i18next";
import i18n from "../../i18next";

export const LanguageSelector = () => {
  const { t } = useTranslation();

  const toggleLanguage = () => {
    const currentLng = i18n.language;
    const newLng = currentLng === "en" ? "es" : "en";
    i18n.changeLanguage(newLng);
  };

  return <SvgButton svg={SVGS.language} onClick={toggleLanguage} />;
};
