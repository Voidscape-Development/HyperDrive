import i18n from "i18next";
import en from "./locales/en.json";

// The app is in English only; the strings stay here so they're in one place
i18n.init({
  lng: "en",
  resources: {
    en: {translations: en},
  },
  ns: ["translations"],
  defaultNS: "translations",
  debug: false,
  interpolation: {escapeValue: false},
});

export default i18n;
