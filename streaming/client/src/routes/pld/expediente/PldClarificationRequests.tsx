import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Button,
  FileInput,
  Group,
  Stack,
  Text,
  Textarea,
} from "@mantine/core";
import { IconUpload } from "@tabler/icons-react";
import {
  answerMyPldClarification,
  TPldClarificationRequest,
  TMyPldExpedient,
  uploadMyPldExpedientDocument,
} from "../../../modules/apiCalls";

const ACCEPT =
  "application/pdf,image/jpeg,image/png,image/webp,application/xml,text/xml,application/zip,.pdf,.jpg,.jpeg,.png,.webp,.xml,.zip";

export function PldClarificationRequests({
  row,
  onSaved,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
}) {
  const { t } = useTranslation();
  const open = (row.clarification_requests || []).filter(
    (item) => item.status === "open"
  );
  if (open.length === 0) return null;

  return (
    <Stack gap="md">
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
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const allowText = item.answer_type !== "document";
  const allowFile = item.answer_type !== "text";

  const submitText = async () => {
    const value = text.trim();
    if (!value) return;
    setBusy(true);
    try {
      const saved = await answerMyPldClarification(rowId, item.id, value);
      onSaved(saved);
      toast.success(t("compliance-clarify-saved"));
    } catch {
      toast.error(t("compliance-clarify-error"));
    } finally {
      setBusy(false);
    }
  };

  const submitFile = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const saved = await uploadMyPldExpedientDocument(rowId, item.slot_key, file);
      onSaved(saved);
      toast.success(t("compliance-clarify-uploaded"));
    } catch {
      toast.error(t("compliance-clarify-error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap="xs" p="sm" style={{ border: "1px solid var(--mantine-color-dark-4)", borderRadius: 8 }}>
      <Text size="sm">{item.prompt}</Text>
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
          <Group>
            <Button size="xs" variant="default" loading={busy} onClick={submitText}>
              {t("compliance-clarify-send-text")}
            </Button>
          </Group>
        </>
      ) : null}
      {allowFile ? (
        <Group align="flex-end">
          <FileInput
            accept={ACCEPT}
            placeholder={t("compliance-clarify-file")}
            value={file}
            onChange={setFile}
            disabled={busy}
            leftSection={<IconUpload size={16} />}
            style={{ flex: 1 }}
          />
          <Button
            size="xs"
            color="violet"
            disabled={!file}
            loading={busy}
            onClick={submitFile}
          >
            {t("compliance-clarify-send-file")}
          </Button>
        </Group>
      ) : null}
    </Stack>
  );
}
