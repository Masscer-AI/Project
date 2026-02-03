import i18n from "i18next";

import translationEN from "./locales/en.json";
import translationES from "./locales/es.json";

let language = localStorage.getItem("language");

if (!language) {
  language = navigator.language;
  if (language) {
    language = language.split("-")[0];
  } else {
    language = "en";
  }
  localStorage.setItem("language", language);
}

const supportedLanguages = ["en", "es"];
if (!supportedLanguages.includes(language)) {
  language = "en";
}

i18n.init({
  resources: {
    en: { translation: translationEN },
    es: { translation: translationES },
  },
  lng: language,
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
