import privacyEn from "../../content/legal/privacy.en.md?raw";
import privacyEs from "../../content/legal/privacy.es.md?raw";
import termsEn from "../../content/legal/terms.en.md?raw";
import termsEs from "../../content/legal/terms.es.md?raw";

export type LegalDocId = "privacy" | "terms";

const LEGAL_DOCS: Record<LegalDocId, { en: string; es: string }> = {
  privacy: { en: privacyEn, es: privacyEs },
  terms: { en: termsEn, es: termsEs },
};

/** Shown on legal pages; bump when markdown content changes. */
export const LEGAL_LAST_UPDATED = "2026-07-20";

export function getLegalMarkdown(docId: LegalDocId, language: string): string {
  const lang = language.startsWith("es") ? "es" : "en";
  return LEGAL_DOCS[docId][lang];
}
