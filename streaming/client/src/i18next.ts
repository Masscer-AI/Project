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

if (import.meta.hot) {
  import.meta.hot.accept(["./locales/en.json", "./locales/es.json"], (mods) => {
    const nextEn = mods?.[0]?.default ?? translationEN;
    const nextEs = mods?.[1]?.default ?? translationES;
    i18n.addResourceBundle("en", "translation", nextEn, true, true);
    i18n.addResourceBundle("es", "translation", nextEs, true, true);
  });
}

export default i18n;
