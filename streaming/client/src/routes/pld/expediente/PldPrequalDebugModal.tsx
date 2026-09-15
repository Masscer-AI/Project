import { Button, Code, Modal, ScrollArea, Stack, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useTranslation } from "react-i18next";
import { TMyPldExpedient } from "../../../modules/apiCalls";

export function PldPrequalDebugModal({
  row,
}: {
  row: TMyPldExpedient;
}) {
  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);
  const findings = row.expedient?.prequalification?.debug?.findings || [];
  const succeeded = row.expedient?.prequalification_status === "succeeded";
  if (!succeeded) return null;

  return (
    <>
      <Button variant="default" size="xs" onClick={open}>
        {t("compliance-prequal-debug")}
      </Button>
      <Modal
        opened={opened}
        onClose={close}
        title={t("compliance-prequal-debug-title")}
        size="lg"
        scrollAreaComponent={ScrollArea.Autosize}
      >
        <Stack gap="sm">
          {findings.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t("compliance-prequal-debug-empty")}
            </Text>
          ) : (
            <Stack gap="md">
              {findings.map((item, index) => (
                <Stack key={`${item.code || "finding"}-${index}`} gap={2}>
                  {item.code ? (
                    <Text size="sm">
                      <Text span c="dimmed">
                        {t("compliance-prequal-debug-code")}
                        {": "}
                      </Text>
                      {item.code}
                    </Text>
                  ) : null}
                  {item.severity ? (
                    <Text size="sm">
                      <Text span c="dimmed">
                        {t("compliance-prequal-debug-severity")}
                        {": "}
                      </Text>
                      {item.severity}
                    </Text>
                  ) : null}
                  {item.target ? (
                    <Text size="sm">
                      <Text span c="dimmed">
                        {t("compliance-prequal-debug-target")}
                        {": "}
                      </Text>
                      {item.target}
                    </Text>
                  ) : null}
                  {item.summary ? <Text size="sm">{item.summary}</Text> : null}
                  {item.evidence ? (
                    <Text size="sm">
                      <Text span c="dimmed">
                        {t("compliance-prequal-debug-evidence")}
                        {": "}
                      </Text>
                      {item.evidence}
                    </Text>
                  ) : null}
                </Stack>
              ))}
            </Stack>
          )}
          <Text size="sm" fw={500}>
            {t("compliance-prequal-debug-raw")}
          </Text>
          <Code block style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {JSON.stringify(row.expedient?.prequalification?.debug ?? {}, null, 2)}
          </Code>
        </Stack>
      </Modal>
    </>
  );
}
