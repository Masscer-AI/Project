import { Code, Modal, ScrollArea, Stack, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { TPldDocumentSlot } from "../../../modules/apiCalls";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function filledText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "si" : "no";
  return null;
}

function formatAddress(value: unknown): string | null {
  const row = asRecord(value);
  if (!row) return filledText(value);
  const parts = [
    row.street,
    row.exterior_number,
    row.interior_number,
    row.neighborhood,
    row.municipality,
    row.city,
    row.state,
    row.postal_code,
    row.country,
    row.raw_text,
  ]
    .map(filledText)
    .filter((part): part is string => Boolean(part));
  return parts.length > 0 ? [...new Set(parts)].join(", ") : null;
}

function formatPeople(value: unknown): string | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const parts = value
    .map((item) => {
      const row = asRecord(item);
      if (!row) return filledText(item);
      const name =
        filledText(row.name) ||
        filledText(row.full_name) ||
        filledText(row.attorney_name) ||
        filledText(row.legal_name_or_full_name);
      const extra =
        filledText(row.ownership_percentage) ||
        filledText(row.role) ||
        filledText(row.rfc);
      if (name && extra) return `${name} (${extra})`;
      return name;
    })
    .filter((part): part is string => Boolean(part));
  return parts.length > 0 ? parts.join(" · ") : null;
}

export function extractionLines(
  payload: Record<string, unknown> | undefined
): { key: string; value: string }[] {
  const row = payload || {};
  const skip = new Set([
    "name_matches_client_hint",
    "photo_present",
    "signature_present",
    "ownership_may_be_stale",
    "provenances",
    "_meta",
  ]);
  const lines: { key: string; value: string }[] = [];
  const push = (key: string, raw: unknown) => {
    if (skip.has(key) || raw == null || raw === "") return;
    if (
      key === "address" ||
      key.endsWith("_address") ||
      key === "tax_address" ||
      key === "service_address" ||
      key === "registered_address"
    ) {
      const formatted = formatAddress(raw);
      if (formatted) lines.push({ key, value: formatted });
      return;
    }
    if (key === "notary") {
      const formatted = formatAddress(raw) || formatPeople([raw]);
      const notary = asRecord(raw);
      const bits = notary
        ? [
            filledText(notary.name),
            filledText(notary.notaria_number),
            filledText(notary.escritura_number),
            filledText(notary.city),
          ].filter((part): part is string => Boolean(part))
        : [];
      if (bits.length > 0) lines.push({ key, value: bits.join(" · ") });
      else if (formatted) lines.push({ key, value: formatted });
      return;
    }
    if (Array.isArray(raw)) {
      if (raw.every((item) => typeof item === "string")) {
        const joined = raw.map(filledText).filter((part): part is string => Boolean(part));
        if (joined.length > 0) lines.push({ key, value: joined.join(" · ") });
        return;
      }
      const formatted = formatPeople(raw);
      if (formatted) lines.push({ key, value: formatted });
      return;
    }
    const text = filledText(raw);
    if (text) lines.push({ key, value: text });
  };
  Object.entries(row).forEach(([key, value]) => push(key, value));
  return lines;
}

export function PldExtractionDebugModal({
  slot,
  opened,
  onClose,
}: {
  slot: TPldDocumentSlot | null;
  opened: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const payload = slot?.document?.extracted_payload;
  const lines = extractionLines(payload);
  const title = slot
    ? t(`compliance-doc-slot-${slot.document_kind}`, {
        name: slot.label_name || "",
        defaultValue: slot.document_kind,
      })
    : t("compliance-extract-debug-title");

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={title}
      size="lg"
      scrollAreaComponent={ScrollArea.Autosize}
    >
      <Stack gap="sm">
        {slot?.document?.original_filename ? (
          <Text size="sm" c="dimmed">
            {slot.document.original_filename}
          </Text>
        ) : null}
        {lines.length === 0 ? (
          <Text size="sm" c="dimmed">
            {t("compliance-extract-debug-empty")}
          </Text>
        ) : (
          <Stack gap={4}>
            {lines.map((line) => (
              <Text key={line.key} size="sm">
                <Text span fw={500}>
                  {t(`compliance-extract-${line.key}`, {
                    defaultValue: line.key.replace(/_/g, " "),
                  })}
                  {": "}
                </Text>
                {line.value}
              </Text>
            ))}
          </Stack>
        )}
        <Text size="sm" fw={500}>
          {t("compliance-extract-debug-raw")}
        </Text>
        <Code block style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {JSON.stringify(payload ?? {}, null, 2)}
        </Code>
      </Stack>
    </Modal>
  );
}
