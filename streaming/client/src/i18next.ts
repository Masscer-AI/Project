import i18n from "i18next";

import translationEN from "./locales/en.json";
import translationES from "./locales/es.json";
import translationIT from "./locales/it.json";

let language = localStorage.getItem("language");


if (!language) {
  // language = navigator.language || navigator.userLanguage; // Get the browser language
  language = navigator.language;
  if (language) {
    
    language = language.split("-")[0]; 
  } else {
    language = "en"; 
  }
  localStorage.setItem("language", language);
}

// Ensure the language is one of the supported languages
const supportedLanguages = ["en", "es", "it"];
if (!supportedLanguages.includes(language)) {
  language = "en"; // Fallback to English if unsupported language
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
