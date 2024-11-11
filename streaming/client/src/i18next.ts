import i18n from "i18next";

import translationEN from "./locales/en.json";
import translationES from "./locales/es.json";
import translationIT from "./locales/it.json";

let language = localStorage.getItem("language");
if (!language) {
  language = "en";
  localStorage.setItem("language", language);
}

i18n.init({
  resources: {
    en: { translation: translationEN },
    es: { translation: translationES },
    it: { translation: translationIT },
  },
  lng: language,
  fallbackLng: "en",
  interpolation: {
    escapeValue: false, // React already does escaping
  },
});

export default i18n;
