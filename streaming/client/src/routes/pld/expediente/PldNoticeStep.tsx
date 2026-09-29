import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { Alert, Badge, Button, Stack, Text } from "@mantine/core";
import { finishMyPldNoticeInvoices, TMyPldExpedient } from "../../../modules/apiCalls";
import { PldDocumentCollection } from "./PldDocumentCollection";

function money(value: number) {
  return value.toLocaleString("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  });
}

function asAmount(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const cleaned = String(value || "").replace(/[^0-9.]/g, "");
  if (!cleaned) return null;
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

export function PldNoticeStep({
  row,
  onSaved,
  onNext,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
  onNext?: () => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const activity = row.vulnerable_activity;
  if (!activity) return null;
  const limit = activity.notice_mxn;
  const invoices = (row.document_slots || []).filter(
    (slot) => slot.document_kind === "cfdi" && slot.document
  );
  return (
    <Stack gap="md">
      <Stack gap={4}>
        <Text fw={600}>{t("compliance-notice-title")}</Text>
        <Text size="sm">
          {t("compliance-notice-activity", {
            fraction: activity.fraction,
            activity: activity.activity,
          })}
        </Text>
        {limit != null && activity.notice_uma != null ? (
          <Text size="sm">
            {t("compliance-notice-limit", {
              uma: activity.notice_uma.toLocaleString("es-MX"),
              money: money(limit),
            })}
          </Text>
        ) : activity.notice_note ? (
          <Text size="sm">{activity.notice_note}</Text>
        ) : null}
      </Stack>
      <PldDocumentCollection
        embedded
        section="notice"
        isMoral={row.person_type === "persona_moral"}
        row={row}
        onSaved={onSaved}
        onContinue={() => undefined}
      />
      {invoices.map((slot) => {
        const total = asAmount(slot.document?.extracted_payload?.total);
        const over = limit != null && total != null && total > limit;
        return (
          <Alert key={slot.slot_key} color={over ? "yellow" : "gray"} variant="light">
            <Text size="sm" fw={600}>
              {slot.document?.original_filename}
            </Text>
            {total == null ? (
              <Text size="sm">{t("compliance-notice-amount-pending")}</Text>
            ) : (
              <Badge mt={6} variant="light" color={over ? "yellow" : "teal"}>
                {over
                  ? t("compliance-notice-over", { money: money(total) })
                  : t("compliance-notice-under", { money: money(total) })}
              </Badge>
            )}
          </Alert>
        );
      })}
      {onNext ? (
        <Button
          color="violet"
          fullWidth
          loading={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const saved = await finishMyPldNoticeInvoices(row.id);
              if (!saved) {
                toast.error(t("compliance-clarify-error"));
                return;
              }
              onSaved(saved);
              onNext();
            } catch {
              toast.error(t("compliance-clarify-error"));
            } finally {
              setBusy(false);
            }
          }}
        >
          {t("compliance-doc-continue")}
        </Button>
      ) : null}
    </Stack>
  );
}
