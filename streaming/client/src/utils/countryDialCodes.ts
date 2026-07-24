/**
 * Country dial-code catalog for phone number pickers.
 * `value` is ISO 3166-1 alpha-2; `dial` is digits only (no +).
 */

export type TCountryDialOption = {
  value: string;
  name: string;
  dial: string;
};

export const COUNTRY_DIAL_CODES: TCountryDialOption[] = [
  { value: "AF", name: "Afghanistan", dial: "93" },
  { value: "AL", name: "Albania", dial: "355" },
  { value: "DZ", name: "Algeria", dial: "213" },
  { value: "AR", name: "Argentina", dial: "54" },
  { value: "AM", name: "Armenia", dial: "374" },
  { value: "AU", name: "Australia", dial: "61" },
  { value: "AT", name: "Austria", dial: "43" },
  { value: "AZ", name: "Azerbaijan", dial: "994" },
  { value: "BS", name: "Bahamas", dial: "1242" },
  { value: "BH", name: "Bahrain", dial: "973" },
  { value: "BD", name: "Bangladesh", dial: "880" },
  { value: "BB", name: "Barbados", dial: "1246" },
  { value: "BY", name: "Belarus", dial: "375" },
  { value: "BE", name: "Belgium", dial: "32" },
  { value: "BZ", name: "Belize", dial: "501" },
  { value: "BO", name: "Bolivia", dial: "591" },
  { value: "BA", name: "Bosnia and Herzegovina", dial: "387" },
  { value: "BR", name: "Brazil", dial: "55" },
  { value: "BG", name: "Bulgaria", dial: "359" },
  { value: "CA", name: "Canada", dial: "1" },
  { value: "CL", name: "Chile", dial: "56" },
  { value: "CN", name: "China", dial: "86" },
  { value: "CO", name: "Colombia", dial: "57" },
  { value: "CR", name: "Costa Rica", dial: "506" },
  { value: "HR", name: "Croatia", dial: "385" },
  { value: "CU", name: "Cuba", dial: "53" },
  { value: "CY", name: "Cyprus", dial: "357" },
  { value: "CZ", name: "Czech Republic", dial: "420" },
  { value: "DK", name: "Denmark", dial: "45" },
  { value: "DO", name: "Dominican Republic", dial: "1809" },
  { value: "EC", name: "Ecuador", dial: "593" },
  { value: "EG", name: "Egypt", dial: "20" },
  { value: "SV", name: "El Salvador", dial: "503" },
  { value: "EE", name: "Estonia", dial: "372" },
  { value: "ET", name: "Ethiopia", dial: "251" },
  { value: "FI", name: "Finland", dial: "358" },
  { value: "FR", name: "France", dial: "33" },
  { value: "DE", name: "Germany", dial: "49" },
  { value: "GH", name: "Ghana", dial: "233" },
  { value: "GR", name: "Greece", dial: "30" },
  { value: "GT", name: "Guatemala", dial: "502" },
  { value: "HN", name: "Honduras", dial: "504" },
  { value: "HK", name: "Hong Kong", dial: "852" },
  { value: "HU", name: "Hungary", dial: "36" },
  { value: "IS", name: "Iceland", dial: "354" },
  { value: "IN", name: "India", dial: "91" },
  { value: "ID", name: "Indonesia", dial: "62" },
  { value: "IE", name: "Ireland", dial: "353" },
  { value: "IL", name: "Israel", dial: "972" },
  { value: "IT", name: "Italy", dial: "39" },
  { value: "JM", name: "Jamaica", dial: "1876" },
  { value: "JP", name: "Japan", dial: "81" },
  { value: "JO", name: "Jordan", dial: "962" },
  { value: "KZ", name: "Kazakhstan", dial: "7" },
  { value: "KE", name: "Kenya", dial: "254" },
  { value: "KW", name: "Kuwait", dial: "965" },
  { value: "LV", name: "Latvia", dial: "371" },
  { value: "LB", name: "Lebanon", dial: "961" },
  { value: "LT", name: "Lithuania", dial: "370" },
  { value: "LU", name: "Luxembourg", dial: "352" },
  { value: "MY", name: "Malaysia", dial: "60" },
  { value: "MT", name: "Malta", dial: "356" },
  { value: "MX", name: "Mexico", dial: "52" },
  { value: "MA", name: "Morocco", dial: "212" },
  { value: "NL", name: "Netherlands", dial: "31" },
  { value: "NZ", name: "New Zealand", dial: "64" },
  { value: "NI", name: "Nicaragua", dial: "505" },
  { value: "NG", name: "Nigeria", dial: "234" },
  { value: "NO", name: "Norway", dial: "47" },
  { value: "PK", name: "Pakistan", dial: "92" },
  { value: "PA", name: "Panama", dial: "507" },
  { value: "PY", name: "Paraguay", dial: "595" },
  { value: "PE", name: "Peru", dial: "51" },
  { value: "PH", name: "Philippines", dial: "63" },
  { value: "PL", name: "Poland", dial: "48" },
  { value: "PT", name: "Portugal", dial: "351" },
  { value: "PR", name: "Puerto Rico", dial: "1787" },
  { value: "QA", name: "Qatar", dial: "974" },
  { value: "RO", name: "Romania", dial: "40" },
  { value: "RU", name: "Russia", dial: "7" },
  { value: "SA", name: "Saudi Arabia", dial: "966" },
  { value: "RS", name: "Serbia", dial: "381" },
  { value: "SG", name: "Singapore", dial: "65" },
  { value: "SK", name: "Slovakia", dial: "421" },
  { value: "SI", name: "Slovenia", dial: "386" },
  { value: "ZA", name: "South Africa", dial: "27" },
  { value: "KR", name: "South Korea", dial: "82" },
  { value: "ES", name: "Spain", dial: "34" },
  { value: "LK", name: "Sri Lanka", dial: "94" },
  { value: "SE", name: "Sweden", dial: "46" },
  { value: "CH", name: "Switzerland", dial: "41" },
  { value: "TW", name: "Taiwan", dial: "886" },
  { value: "TH", name: "Thailand", dial: "66" },
  { value: "TT", name: "Trinidad and Tobago", dial: "1868" },
  { value: "TN", name: "Tunisia", dial: "216" },
  { value: "TR", name: "Turkey", dial: "90" },
  { value: "UA", name: "Ukraine", dial: "380" },
  { value: "AE", name: "United Arab Emirates", dial: "971" },
  { value: "GB", name: "United Kingdom", dial: "44" },
  { value: "US", name: "United States", dial: "1" },
  { value: "UY", name: "Uruguay", dial: "598" },
  { value: "VE", name: "Venezuela", dial: "58" },
  { value: "VN", name: "Vietnam", dial: "84" },
];

/** Prefer these ISO codes when several countries share a dial code. */
const DIAL_PREFERRED_ISO: Record<string, string> = {
  "1": "US",
  "7": "RU",
};

const byIso = new Map(COUNTRY_DIAL_CODES.map((c) => [c.value, c]));

export function getCountryByIso(iso: string): TCountryDialOption | undefined {
  return byIso.get((iso || "").toUpperCase());
}

export function getDialCodeForIso(iso: string): string {
  return getCountryByIso(iso)?.dial || "";
}

/** Resolve a stored dial-code string to the best matching ISO country. */
export function isoFromDialCode(dial: string): string | null {
  const digits = (dial || "").replace(/\D/g, "");
  if (!digits) return null;
  const preferred = DIAL_PREFERRED_ISO[digits];
  if (preferred && byIso.has(preferred)) return preferred;
  const match = COUNTRY_DIAL_CODES.find((c) => c.dial === digits);
  return match?.value ?? null;
}

export function countrySelectData() {
  return COUNTRY_DIAL_CODES.map((c) => ({
    value: c.value,
    // Include ISO + dial so users can search "EC", "Mexico", "+52", etc.
    label: `${c.name} (${c.value}, +${c.dial})`,
  }));
}
