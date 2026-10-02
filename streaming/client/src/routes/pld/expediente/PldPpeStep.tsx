import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { Alert, Badge, Button, Card, Group, Loader, Stack, Text } from "@mantine/core";
import { IconCircleCheck } from "@tabler/icons-react";
import { rerunMyPldPpe, TMyPldExpedient } from "../../../modules/apiCalls";

export function PldPpeStep({
  row,
  onSaved,
  onContinue,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
  onContinue?: () => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const status = row.expedient?.ppe_status || "";
  const checks = row.expedient?.ppe?.checks || [];
  const clear = status === "succeeded" && checks.every((item) => item.hit_count === 0);

  const retry = async () => {
    setBusy(true);
    try {
      const next = await rerunMyPldPpe(row.id);
      onSaved(next);
    } catch {
      toast.error(t("compliance-ppe-retry-error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap="sm">
      {status === "pending" || status === "" ? (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-ppe-running")}
        </Alert>
      ) : null}
      {status === "failed" ? (
        <Stack gap="sm">
          <Alert color="red" variant="light">
            {t("compliance-ppe-failed")}
          </Alert>
          <Button variant="default" loading={busy} onClick={() => void retry()}>
            {t("compliance-ppe-retry")}
          </Button>
        </Stack>
      ) : null}
      {status === "succeeded" && clear ? (
        <Alert color="teal" variant="light" icon={<IconCircleCheck size={18} />}>
          {t("compliance-ppe-clear")}
        </Alert>
      ) : null}
      {status === "succeeded"
        ? checks.map((check) => (
            <Card key={`${check.role}-${check.name}`} withBorder radius="md" p="sm">
              <Group justify="space-between" align="flex-start" wrap="nowrap" gap="sm">
                <Stack gap={2} style={{ minWidth: 0 }}>
                  <Text size="xs" c="dimmed">
                    {t(`compliance-screening-role-${check.role}`)}
                  </Text>
                  <Text size="sm" fw={600} style={{ overflowWrap: "anywhere" }}>
                    {check.name}
                  </Text>
                  {check.hit_count > 0 && check.top_caption ? (
                    <Text size="xs" c="dimmed">
                      {check.top_caption}
                    </Text>
                  ) : null}
                </Stack>
                <Badge
                  variant="light"
                  color={check.hit_count === 0 ? "teal" : "red"}
                  style={{ flexShrink: 0, textTransform: "none" }}
                >
                  {check.hit_count === 0
                    ? t("compliance-screening-hits_zero")
                    : t("compliance-screening-hits", { count: check.hit_count })}
                </Badge>
              </Group>
            </Card>
          ))
        : null}
      {onContinue ? (
        <Button
          color="violet"
          fullWidth
          disabled={status !== "succeeded"}
          onClick={onContinue}
        >
          {t("compliance-doc-continue")}
        </Button>
      ) : null}
    </Stack>
  );
}
