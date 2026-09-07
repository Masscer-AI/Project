import { State } from "country-state-city";

function normalizePlaceName(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export function subdivisionsForCountry(iso: string): string[] | null {
  const states = State.getStatesOfCountry((iso || "").toUpperCase());
  if (!states.length) return null;
  return states.map((state) => state.name);
}

export function matchSubdivisionName(iso: string, raw: string): string {
  const trimmed = (raw || "").trim();
  if (!trimmed) return "";
  const list = subdivisionsForCountry(iso);
  if (!list) return trimmed;
  const exact = list.find((name) => name === trimmed);
  if (exact) return exact;
  const normalized = normalizePlaceName(trimmed);
  return list.find((name) => normalizePlaceName(name) === normalized) || trimmed;
}

export function subdivisionSelectData(iso: string, current = "") {
  const list = subdivisionsForCountry(iso);
  if (!list) return null;
  const options = list.map((name) => ({ value: name, label: name }));
  const trimmed = current.trim();
  if (trimmed && !list.includes(trimmed)) {
    return [{ value: trimmed, label: trimmed }, ...options];
  }
  return options;
}
