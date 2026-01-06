import React, { useState } from "react";

import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { useTranslation } from "react-i18next";
import i18n from "../../i18next";
import { FloatingDropdown } from "../Dropdown/Dropdown";

export const LanguageSelector = () => {
  const { t } = useTranslation();

  const [isOpened, setIsOpened] = useState(false);
  const [hoveredLanguage, setHoveredLanguage] = useState<string | null>(null);
  const toggleLanguage = () => {
    setIsOpened(!isOpened);
  };

  const setLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    setIsOpened(false);
    localStorage.setItem("language", lng);
  };

  const possibleLanguages = ["en", "es", "it", "nah"];

  return (
    <div className="pos-relative" style={{ width: "fit-content" }}>
      <FloatingDropdown
        // bottom="100%"
        left="100%"
        isOpened={isOpened}
        opener={
          <SvgButton
            text={t("language")}
            svg={SVGS.language}
            onClick={toggleLanguage}
            extraClass="pos-relative"
          />
        }
      >
        <div className="w-[200px] flex flex-col gap-2 p-3 bg-black/95 backdrop-blur-sm border border-gray-700 rounded-xl shadow-lg">
          {possibleLanguages.map((lng) => (
            <button
              key={lng}
              className={`px-4 py-2 rounded-lg font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-between ${
                hoveredLanguage === lng 
                  ? 'bg-gray-800 text-white border-gray-600' 
                  : 'bg-transparent text-gray-300 border-transparent hover:bg-gray-900'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredLanguage(lng)}
              onMouseLeave={() => setHoveredLanguage(null)}
              onClick={() => setLanguage(lng)}
            >
              <span className="text-xs text-gray-400 font-mono">{lng}</span>
              <span>{t(lng)}</span>
            </button>
          ))}
        </div>
      </FloatingDropdown>
    </div>
  );
};
