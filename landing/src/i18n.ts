import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import translationEN from "./locales/en.json";
import translationES from "./locales/es.json";

const SUPPORTED = ["en", "es"] as const;
export type Lang = (typeof SUPPORTED)[number];

const STORAGE_KEY = "language";

function detectLanguage(): Lang {
  let language = localStorage.getItem(STORAGE_KEY);
  if (!language) {
    language = (navigator.language || "en").split("-")[0];
    localStorage.setItem(STORAGE_KEY, language);
  }
  if (!SUPPORTED.includes(language as Lang)) {
    language = "en";
    localStorage.setItem(STORAGE_KEY, language);
  }
  return language as Lang;
}

const language = detectLanguage();

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: translationEN },
    es: { translation: translationES },
  },
  lng: language,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

document.documentElement.lang = language;

i18n.on("languageChanged", (lng) => {
  localStorage.setItem(STORAGE_KEY, lng);
  document.documentElement.lang = lng;
});

export function setLanguage(lang: Lang) {
  void i18n.changeLanguage(lang);
}

export default i18n;
