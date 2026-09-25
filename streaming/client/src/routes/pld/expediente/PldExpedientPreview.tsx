import { Fragment, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Loader, Modal, Stack, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconEye } from "@tabler/icons-react";
import { fetchMyPldPacketPages, TMyPldExpedient, TPldDocumentSlot } from "../../../modules/apiCalls";
import { extractionSummary } from "./PldExtractionDebugModal";

function asText(value: unknown): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function SheetRows({ rows }: { rows: { label: string; value: string }[] }) {
  const filled = rows.filter((row) => row.value);
  if (filled.length === 0) return null;
  return (
    <dl>
      {filled.map((row) => (
        <Fragment key={row.label}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </Fragment>
      ))}
    </dl>
  );
}

function slotTitle(
  t: (key: string, options?: Record<string, unknown>) => string,
  slot: TPldDocumentSlot
) {
  if (slot.document_kind === "cfdi" && slot.label_name) {
    return t("compliance-doc-slot-cfdi-extra", { name: slot.label_name });
  }
  return t(`compliance-doc-slot-${slot.document_kind}`, {
    name: slot.label_name || "",
    defaultValue: slot.document_kind,
  });
}

export function PldExpedientPreview({
  row,
  fullWidth,
}: {
  row: TMyPldExpedient;
  fullWidth?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);
  const [pages, setPages] = useState<string[]>([]);
  const [pdfError, setPdfError] = useState(false);
  const packetStatus = row.expedient?.packet_status || "";
  const packetReady =
    packetStatus !== "writing" &&
    (packetStatus === "ready" || Boolean(row.expedient?.packet_ready));

  useEffect(() => {
    if (!opened || !packetReady) return;
    let cancelled = false;
    setPdfError(false);
    setPages([]);
    void fetchMyPldPacketPages(row.id)
      .then((data) => {
        if (!cancelled) setPages(data.pages || []);
      })
      .catch(() => {
        if (!cancelled) setPdfError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [opened, packetReady, row.id]);
  const meta = asRecord(row.metadata);
  const address = asRecord(meta.address);
  const representative = asRecord(meta.representative);
  const repId = asRecord(representative.identification);
  const identification = asRecord(meta.identification);
  const isMoral = row.person_type === "persona_moral";
  const controllers = Array.isArray(meta.controllers) ? meta.controllers : [];
  const uploadedSlots = (row.document_slots || []).filter((slot) => slot.document);
  const displayName =
    asText(meta.legal_name) ||
    [asText(meta.given_names), asText(meta.surnames)].filter(Boolean).join(" ") ||
    row.name;
  const prepared = new Date().toLocaleDateString(i18n.language, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <>
      <Button
        variant="default"
        fullWidth={fullWidth}
        leftSection={fullWidth ? <IconEye size={16} /> : undefined}
        onClick={open}
      >
        {t("compliance-dossier-preview")}
      </Button>
      <Modal
        opened={opened}
        onClose={close}
        size="xl"
        title={t("compliance-dossier-preview")}
        styles={{
          content: { background: "#d9d3c7" },
          header: { background: "#d9d3c7" },
          body: { background: "#d9d3c7", overflowX: "hidden" },
          title: { color: "#1c1915" },
        }}
      >
        {packetReady ? (
          pdfError ? (
            <Text c="dark">{t("compliance-packet-failed")}</Text>
          ) : pages.length > 0 ? (
            <Stack gap="md">
              {pages.map((src, index) => (
                <img
                  key={index}
                  src={src}
                  alt=""
                  style={{ width: "100%", background: "#fff", display: "block" }}
                />
              ))}
            </Stack>
          ) : (
            <Loader size={16} type="oval" color="dark" />
          )
        ) : packetStatus === "writing" || packetStatus === "failed" ? (
          <Group gap="xs">
            {packetStatus === "writing" ? (
              <Loader size={16} type="oval" color="dark" />
            ) : null}
            <Text c="dark">
              {t(
                packetStatus === "failed"
                  ? "compliance-packet-failed"
                  : "compliance-packet-writing"
              )}
            </Text>
          </Group>
        ) : (
        <article className="pld-sheet">
          <style>{`
            .pld-sheet {
              background: #fffef8;
              color: #1c1915;
              font-family: Georgia, "Times New Roman", serif;
              padding: 3rem 3.25rem;
              box-shadow: 0 12px 40px rgba(40, 32, 20, 0.18);
              line-height: 1.45;
              max-width: 100%;
              box-sizing: border-box;
              overflow-wrap: anywhere;
            }
            .pld-sheet header {
              border-bottom: 2px solid #1c1915;
              padding-bottom: 1rem;
              margin-bottom: 1.5rem;
            }
            .pld-sheet h1 {
              font-size: 1.65rem;
              font-weight: 600;
              margin: 0 0 0.35rem;
              letter-spacing: 0.01em;
            }
            .pld-sheet h2 {
              font-size: 1.05rem;
              font-weight: 600;
              margin: 1.6rem 0 0.7rem;
              padding-bottom: 0.25rem;
              border-bottom: 1px solid #cfc6b8;
            }
            .pld-sheet p {
              margin: 0.15rem 0;
            }
            .pld-sheet .pld-kicker {
              font-family: system-ui, sans-serif;
              font-size: 0.75rem;
              letter-spacing: 0.08em;
              text-transform: uppercase;
              color: #6b6256;
              margin: 0 0 0.4rem;
            }
            .pld-sheet dl {
              display: grid;
              grid-template-columns: 13rem 1fr;
              gap: 0.35rem 1rem;
              margin: 0;
            }
            .pld-sheet dt {
              margin: 0;
              color: #6b6256;
              font-family: system-ui, sans-serif;
              font-size: 0.82rem;
            }
            .pld-sheet dd {
              margin: 0;
            }
            .pld-sheet table {
              width: 100%;
              border-collapse: collapse;
              font-size: 0.95rem;
              table-layout: fixed;
            }
            .pld-sheet th,
            .pld-sheet td {
              text-align: left;
              vertical-align: top;
              padding: 0.45rem 0.4rem;
              border-bottom: 1px solid #e4dccf;
              overflow-wrap: anywhere;
            }
            .pld-sheet th {
              font-family: system-ui, sans-serif;
              font-size: 0.75rem;
              letter-spacing: 0.04em;
              text-transform: uppercase;
              color: #6b6256;
              font-weight: 600;
            }
            .pld-sheet .pld-note {
              display: block;
              margin-top: 0.2rem;
              color: #4a453d;
              font-size: 0.88rem;
              overflow-wrap: anywhere;
            }
            .pld-sheet .pld-doc {
              padding: 0.7rem 0;
              border-bottom: 1px solid #e4dccf;
            }
            .pld-sheet .pld-doc p {
              margin: 0;
            }
            @media (max-width: 40em) {
              .pld-sheet { padding: 1.4rem 1.1rem; }
              .pld-sheet dl { grid-template-columns: 1fr; gap: 0.1rem 0; }
              .pld-sheet dd { margin-bottom: 0.55rem; }
            }
          `}</style>
          <header>
            <p className="pld-kicker">{row.organization_name}</p>
            <h1>{t("compliance-dossier-title")}</h1>
            <p>{displayName}</p>
            <p className="pld-kicker">
              {t(`compliance-person-${row.person_type}`, {
                defaultValue: row.person_type,
              })}
              {" · "}
              {prepared}
            </p>
          </header>
          <section>
            <h2>{t("compliance-dossier-identity")}</h2>
            <SheetRows
              rows={
                isMoral
                  ? [
                      { label: t("compliance-intake-legal-name"), value: asText(meta.legal_name) },
                      { label: t("compliance-intake-constitution-date"), value: asText(meta.constitution_date) },
                      { label: t("compliance-intake-nationality"), value: asText(meta.nationality) },
                      { label: t("compliance-intake-rfc-entity"), value: asText(meta.rfc) },
                      { label: t("compliance-intake-activity"), value: asText(meta.economic_activity) },
                      { label: t("compliance-intake-phone"), value: asText(meta.phone) },
                      { label: t("email"), value: asText(meta.email) },
                    ]
                  : [
                      { label: t("compliance-intake-given-names"), value: asText(meta.given_names) },
                      { label: t("compliance-intake-surnames"), value: asText(meta.surnames) },
                      { label: t("compliance-intake-date-of-birth"), value: asText(meta.date_of_birth) },
                      { label: t("compliance-intake-country-of-birth"), value: asText(meta.country_of_birth) },
                      { label: t("compliance-intake-nationality"), value: asText(meta.nationality) },
                      { label: "CURP", value: asText(meta.curp) },
                      { label: t("compliance-intake-rfc-person"), value: asText(meta.rfc) },
                      { label: t("compliance-intake-activity"), value: asText(meta.economic_activity) },
                      { label: t("compliance-intake-phone"), value: asText(meta.phone) },
                      { label: t("email"), value: asText(meta.email) },
                      { label: t("compliance-intake-id-type"), value: asText(identification.document_type) },
                      { label: t("compliance-intake-id-number"), value: asText(identification.document_number) },
                    ]
              }
            />
          </section>
          <section>
            <h2>{t("compliance-intake-address")}</h2>
            <SheetRows
              rows={[
                { label: t("compliance-intake-street"), value: asText(address.street) },
                { label: t("compliance-intake-ext-number"), value: asText(address.exterior_number) },
                { label: t("compliance-intake-neighborhood"), value: asText(address.neighborhood) },
                { label: t("compliance-intake-municipality"), value: asText(address.municipality) },
                { label: t("compliance-intake-city"), value: asText(address.city) },
                { label: t("compliance-intake-state"), value: asText(address.state) },
                { label: t("compliance-intake-postal-code"), value: asText(address.postal_code) },
                { label: t("compliance-intake-country"), value: asText(address.country) },
              ]}
            />
          </section>
          {isMoral ? (
            <section>
              <h2>{t("compliance-intake-representative")}</h2>
              <SheetRows
                rows={[
                  { label: t("compliance-intake-given-names"), value: asText(representative.given_names) },
                  { label: t("compliance-intake-surnames"), value: asText(representative.surnames) },
                  { label: t("compliance-intake-date-of-birth"), value: asText(representative.date_of_birth) },
                  { label: t("compliance-intake-rfc-representative"), value: asText(representative.rfc) },
                  { label: "CURP", value: asText(representative.curp) },
                  { label: t("compliance-intake-id-type"), value: asText(repId.document_type) },
                  { label: t("compliance-intake-id-number"), value: asText(repId.document_number) },
                ]}
              />
            </section>
          ) : null}
          <section>
            <h2>{t("compliance-intake-controller")}</h2>
            {controllers.length === 0 ? (
              <p>{t("compliance-dossier-controller-empty")}</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>{t("compliance-intake-controller-name")}</th>
                    <th>{t("compliance-intake-rfc-controller")}</th>
                    <th>{t("email")}</th>
                    <th>{t("compliance-intake-ownership")}</th>
                  </tr>
                </thead>
                <tbody>
                  {controllers.map((item, index) => {
                    const person = asRecord(item);
                    return (
                      <tr key={`${asText(person.name)}-${index}`}>
                        <td>{asText(person.name)}</td>
                        <td>{asText(person.rfc)}</td>
                        <td>{asText(person.email)}</td>
                        <td>{asText(person.ownership_percentage)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </section>
          {uploadedSlots.length > 0 ? (
          <section>
            <h2>{t("compliance-dossier-preview-documents")}</h2>
            {uploadedSlots.map((slot) => {
              const summary = extractionSummary(slot.document?.extracted_payload);
              const status =
                slot.document?.extraction_status === "succeeded"
                  ? t("compliance-dossier-extracted")
                  : t("compliance-dossier-extract-pending");
              return (
                <div className="pld-doc" key={slot.slot_key}>
                  <p>{slotTitle(t, slot)}</p>
                  {slot.document?.original_filename ? (
                    <span className="pld-note">{slot.document.original_filename}</span>
                  ) : null}
                  {summary ? <span className="pld-note">{summary}</span> : null}
                  <span className="pld-kicker">{status}</span>
                </div>
              );
            })}
          </section>
          ) : null}
        </article>
        )}
      </Modal>
    </>
  );
}
