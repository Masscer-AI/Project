import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Badge,
  Button,
  FileInput,
  Group,
  Loader,
  Stack,
  Text,
  Textarea,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconUpload } from "@tabler/icons-react";
import {
  answerMyPldClarification,
  TPldClarificationRequest,
  TMyPldExpedient,
  TPldDocumentSlot,
  uploadMyPldExpedientDocument,
} from "../../../modules/apiCalls";
import { extractionSummary, PldExtractionDebugModal } from "./PldExtractionDebugModal";

const ACCEPT =
  "application/pdf,image/jpeg,image/png,image/webp,application/xml,text/xml,application/zip,.pdf,.jpg,.jpeg,.png,.webp,.xml,.zip";

function clarificationSlot(item: TPldClarificationRequest): TPldDocumentSlot | null {
  if (!item.document) return null;
  return {
    slot_key: item.slot_key,
    document_kind: "clarification",
    required: false,
    document: item.document,
  };
}

function ClarificationDocument({ item }: { item: TPldClarificationRequest }) {
  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);
  const slot = clarificationSlot(item);
  const doc = item.document;
  if (!doc) return null;
  const summary = extractionSummary(doc.extracted_payload);
  const ready = doc.extraction_status === "succeeded";
  return (
    <>
      {doc.original_filename ? (
        <Text size="sm" c="dimmed">
          {doc.original_filename}
        </Text>
      ) : null}
      {summary ? (
        <Text size="sm" c="dimmed">
          {summary}
        </Text>
      ) : null}
      {ready ? (
        <Badge variant="light" color="teal" w="fit-content" style={{ cursor: "pointer" }} onClick={open}>
          {t("compliance-dossier-extracted")}
        </Badge>
      ) : null}
      <PldExtractionDebugModal slot={slot} opened={opened} onClose={close} />
    </>
  );
}

export function PldClarificationRequests({
  row,
  onSaved,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
}) {
  const { t } = useTranslation();
  const requests = row.clarification_requests || [];
  const open = requests.filter((item) => item.status === "open");
  const answered = requests.filter((item) => item.status !== "open");
  if (requests.length === 0) return null;

  return (
    <Stack gap="md">
      {answered.length > 0 ? (
        <Stack gap="xs">
          <Text size="sm" fw={600}>
            {t("compliance-clarify-history")}
          </Text>
          {answered.map((item) => (
            <Stack
              key={item.id}
              gap={4}
              p="sm"
              style={{ border: "1px solid var(--mantine-color-dark-4)", borderRadius: 8 }}
            >
              <Text size="sm">{item.prompt}</Text>
              {item.text_answer ? (
                <Text size="sm" c="dimmed">
                  {item.text_answer}
                </Text>
              ) : null}
              <ClarificationDocument item={item} />
            </Stack>
          ))}
        </Stack>
      ) : null}
      {open.length > 0 ? (
        <>
          <Text size="sm" fw={600}>
            {t("compliance-clarify-title")}
          </Text>
          <Text size="sm" c="dimmed">
            {t("compliance-clarify-intro")}
          </Text>
          {open.map((item) => (
            <ClarificationCard
              key={item.id}
              rowId={row.id}
              item={item}
              onSaved={onSaved}
            />
          ))}
        </>
      ) : null}
    </Stack>
  );
}

function ClarificationCard({
  rowId,
  item,
  onSaved,
}: {
  rowId: string;
  item: TPldClarificationRequest;
  onSaved: (next: TMyPldExpedient) => void;
}) {
  const { t, i18n } = useTranslation();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const allowText = item.answer_type !== "document";
  const allowFile = item.answer_type !== "text";
  const reading =
    item.document?.extraction_status === "pending" || item.text_review === "reviewing";
  const readFailed = item.document?.extraction_status === "failed";
  const rejected =
    (item.document?.extraction_status === "succeeded" &&
      item.document?.extracted_payload?.is_valid === false) ||
    item.text_review === "rejected";

  const submit = async () => {
    const value = text.trim();
    if (!value && !file) return;
    setBusy(true);
    try {
      if (file) {
        const uploaded = await uploadMyPldExpedientDocument(
          rowId,
          item.slot_key,
          file,
          i18n.language
        );
        onSaved(uploaded);
      }
      if (value) {
        const saved = await answerMyPldClarification(rowId, item.id, value);
        onSaved(saved);
      }
      toast.success(t("compliance-clarify-saved"));
    } catch {
      toast.error(t("compliance-clarify-error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap="xs" p="sm" style={{ border: "1px solid var(--mantine-color-dark-4)", borderRadius: 8 }}>
      <Text size="sm">{item.prompt}</Text>
      {reading ? (
        <Group gap="xs">
          <Loader size={16} type="oval" color="violet" />
          <Text size="sm">
            {t(
              item.text_review === "reviewing"
                ? "compliance-clarify-reviewing"
                : "compliance-clarify-reading"
            )}
          </Text>
        </Group>
      ) : (
        <>
      {readFailed ? (
        <Text size="sm" c="red">
          {t("compliance-clarify-read-failed")}
        </Text>
      ) : null}
      {rejected ? (
        <Text size="sm" c="yellow">
          {t("compliance-clarify-not-valid")}
        </Text>
      ) : null}
      {item.text_review === "rejected" && item.text_answer ? (
        <Text size="sm" c="dimmed">
          {item.text_answer}
        </Text>
      ) : null}
      {item.document && !reading ? <ClarificationDocument item={item} /> : null}
      {allowText ? (
        <>
          <Textarea
            autosize
            minRows={2}
            value={text}
            disabled={busy}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setText(val);
            }}
          />
        </>
      ) : null}
      {allowFile ? (
        <FileInput
          accept={ACCEPT}
          placeholder={t("compliance-clarify-file")}
          value={file}
          onChange={setFile}
          disabled={busy}
          leftSection={<IconUpload size={16} />}
        />
      ) : null}
      <Group>
        <Button
          size="xs"
          color="violet"
          loading={busy}
          disabled={!text.trim() && !file}
          onClick={submit}
        >
          {t("compliance-clarify-send-text")}
        </Button>
      </Group>
        </>
      )}
    </Stack>
  );
}
