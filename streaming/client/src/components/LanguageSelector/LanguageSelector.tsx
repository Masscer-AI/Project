import React, { useState } from "react";

import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { useTranslation } from "react-i18next";
import i18n from "../../i18next";
import { FloatingDropdown } from "../Dropdown/Dropdown";

export const LanguageSelector = () => {
  const { t } = useTranslation();
  const [isOpened, setIsOpened] = useState(false);
  const toggleLanguage = () => {
    // const currentLng = i18n.language;
    // const newLng = currentLng === "en" ? "es" : "en";
    // i18n.changeLanguage(newLng);
    setIsOpened(!isOpened);
  };

  const setLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    setIsOpened(false);
  };
  return (
    <FloatingDropdown
      bottom="100%"
      left="100%"
      isOpened={isOpened}
      opener={
        <SvgButton
          text={t("language")}
          svg={SVGS.language}
          onClick={toggleLanguage}
        />
      }
    >
      <SvgButton
      size="big"
        text={t("english")}
        onClick={() => setLanguage("en")}
        svg={SVGS.language}
      />
      <SvgButton
        size="big"
        text={t("spanish")}
        onClick={() => setLanguage("es")}
        svg={SVGS.language}
      />
      <SvgButton
        size="big"
        text={t("italian")}
        onClick={() => setLanguage("it")}
        svg={SVGS.language}
      />
    </FloatingDropdown>
  );
};
