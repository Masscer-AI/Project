import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Badge,
  Button,
  Card,
  Group,
  Modal,
  NativeSelect,
  NumberInput,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconPlus } from "@tabler/icons-react";
import {
  createPldMatrixProfile,
  deletePldMatrixProfile,
  TPldMatrix,
  TPldMatrixRow,
  updatePldMatrixProfile,
} from "../../modules/apiCalls";

const KINDS: TPldMatrixRow["kind"][] = ["weight", "adjustment", "cutoff"];

type Draft = {
  name: string;
  is_default: boolean;
  points: Record<string, number>;
};

function basePoints(matrix: TPldMatrix): Record<string, number> {
  return Object.fromEntries(matrix.rows.map((row) => [row.slug, row.points]));
}

function formatPoints(value: number): string {
  return String(Math.round(value * 100) / 100);
}

function rowHelpValues(row: TPldMatrixRow, value: number) {
  if (row.kind !== "weight") return { points: formatPoints(value) };
  return {
    p1: formatPoints(value * 0.25),
    p2: formatPoints(value * 0.5),
    p3: formatPoints(value * 0.75),
    p4: formatPoints(value),
  };
}

function weightSum(matrix: TPldMatrix, points: Record<string, number>): number {
  const total = matrix.rows
    .filter((row) => row.kind === "weight")
    .reduce((sum, row) => sum + (Number(points[row.slug]) || 0), 0);
  return Math.round(total * 100) / 100;
}

export function RiskMatrixPanel({
  matrix,
  onChange,
}: {
  matrix: TPldMatrix | null;
  onChange: (matrix: TPldMatrix) => void;
}) {
  const { t } = useTranslation();
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [newName, setNewName] = useState("");
  const [createOpened, { open: openCreate, close: closeCreate }] =
    useDisclosure(false);
  const [deleteOpened, { open: openDelete, close: closeDelete }] =
    useDisclosure(false);

  const profile = matrix?.profiles.find((row) => row.id === selectedId) || null;
  const editable = Boolean(matrix?.can_edit && profile);

  useEffect(() => {
    if (!matrix) return;
    if (selectedId && !profile) {
      setSelectedId("");
      return;
    }
    setDraft(
      profile
        ? {
            name: profile.name,
            is_default: profile.is_default,
            points: { ...profile.points },
          }
        : { name: "", is_default: false, points: basePoints(matrix) }
    );
  }, [matrix, selectedId]);

  const showError = (error: any) => {
    const code = error?.response?.data?.error;
    toast.error(
      t(`compliance-matrix-error-${code}`, {
        defaultValue: t("compliance-matrix-save-error"),
      })
    );
  };

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setSaving(true);
    try {
      const next = await createPldMatrixProfile({ name });
      onChange(next);
      const created = next.profiles.find((row) => row.name === name);
      if (created) setSelectedId(created.id);
      setNewName("");
      closeCreate();
      toast.success(t("compliance-matrix-created"));
    } catch (error) {
      showError(error);
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!profile || !draft) return;
    setSaving(true);
    try {
      onChange(await updatePldMatrixProfile(profile.id, draft));
      toast.success(t("compliance-matrix-saved"));
    } catch (error) {
      showError(error);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      onChange(await deletePldMatrixProfile(profile.id));
      setSelectedId("");
      closeDelete();
      toast.success(t("compliance-matrix-deleted"));
    } catch (error) {
      showError(error);
    } finally {
      setSaving(false);
    }
  };

  if (!matrix || !draft) return null;

  const sum = weightSum(matrix, draft.points);

  return (
    <Stack gap="lg">
      <Card withBorder p="lg">
        <Group justify="space-between" align="flex-end" wrap="wrap">
          <NativeSelect
            label={t("compliance-matrix-profile")}
            style={{ flex: 1, minWidth: "14rem", maxWidth: "24rem" }}
            value={selectedId}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setSelectedId(val);
            }}
            data={[
              { value: "", label: t("compliance-matrix-base") },
              ...matrix.profiles.map((row) => ({
                value: row.id,
                label: row.is_default
                  ? `${row.name} (${t("compliance-matrix-default")})`
                  : row.name,
              })),
            ]}
          />
          {matrix.can_edit ? (
            <Button leftSection={<IconPlus size={14} />} onClick={openCreate}>
              {t("compliance-matrix-new")}
            </Button>
          ) : null}
        </Group>
        <Text size="sm" c="dimmed" mt="sm">
          {profile
            ? t("compliance-matrix-used-by", { count: profile.entity_count })
            : t("compliance-matrix-base-help")}
        </Text>
        {matrix.can_edit ? null : (
          <Text size="sm" c="dimmed" mt="xs">
            {t("compliance-matrix-owner-only")}
          </Text>
        )}
      </Card>

      <Card withBorder p="lg">
        <Title order={5} mb="xs">
          {t("compliance-matrix-how-title")}
        </Title>
        <Stack gap={6}>
          {["step-1", "step-2", "step-3", "lower", "when"].map((key) => (
            <Text key={key} size="sm" c="dimmed">
              {t(`compliance-matrix-how-${key}`)}
            </Text>
          ))}
        </Stack>
      </Card>

      {editable ? (
        <Card withBorder p="lg">
          <Group align="flex-end" wrap="wrap">
            <TextInput
              label={t("name")}
              style={{ flex: 1, minWidth: "14rem" }}
              value={draft.name}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setDraft((current) => current && { ...current, name: val });
              }}
            />
            <Switch
              mb={6}
              label={t("compliance-matrix-default-toggle")}
              checked={draft.is_default}
              onChange={(e) => {
                const checked = e.currentTarget.checked;
                setDraft((current) => current && { ...current, is_default: checked });
              }}
            />
          </Group>
        </Card>
      ) : null}

      {KINDS.map((kind) => (
        <Card key={kind} withBorder p="lg">
          <Group justify="space-between" mb="xs">
            <Title order={5}>{t(`compliance-matrix-kind-${kind}`)}</Title>
            {kind === "weight" ? (
              <Badge variant="light" color={sum === 100 ? "teal" : "red"}>
                {t("compliance-matrix-weight-sum", { sum })}
              </Badge>
            ) : null}
          </Group>
          <Text size="sm" c="dimmed" mb="md">
            {t(`compliance-matrix-kind-${kind}-help`)}
          </Text>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg" verticalSpacing="md">
            {matrix.rows
              .filter((row) => row.kind === kind)
              .map((row) => (
                <Group
                  key={row.slug}
                  justify="space-between"
                  align="flex-start"
                  wrap="nowrap"
                >
                  <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
                    <Text size="sm" fw={500}>
                      {t(`compliance-matrix-row-${row.slug}`, { defaultValue: row.name })}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {t(
                        `compliance-matrix-row-${row.slug}-help`,
                        rowHelpValues(row, Number(draft.points[row.slug]) || 0)
                      )}
                    </Text>
                  </Stack>
                  <NumberInput
                    w="6rem"
                    min={0}
                    max={100}
                    decimalScale={2}
                    disabled={!editable}
                    value={draft.points[row.slug] ?? 0}
                    onChange={(value) =>
                      setDraft(
                        (current) =>
                          current && {
                            ...current,
                            points: { ...current.points, [row.slug]: Number(value) || 0 },
                          }
                      )
                    }
                  />
                </Group>
              ))}
          </SimpleGrid>
        </Card>
      ))}

      {editable ? (
        <Group justify="flex-end">
          <Button color="red" variant="light" onClick={openDelete} disabled={saving}>
            {t("delete")}
          </Button>
          <Button loading={saving} onClick={() => void handleSave()}>
            {t("compliance-matrix-save")}
          </Button>
        </Group>
      ) : null}

      <Modal
        opened={createOpened}
        onClose={closeCreate}
        title={t("compliance-matrix-new")}
        centered
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            {t("compliance-matrix-new-help")}
          </Text>
          <TextInput
            label={t("name")}
            value={newName}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setNewName(val);
            }}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={closeCreate} disabled={saving}>
              {t("cancel")}
            </Button>
            <Button loading={saving} onClick={() => void handleCreate()}>
              {t("compliance-matrix-new")}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={deleteOpened}
        onClose={closeDelete}
        title={t("compliance-matrix-delete-title")}
        centered
      >
        <Stack gap="md">
          <Text size="sm">
            {t("compliance-matrix-delete-description", { name: profile?.name || "" })}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={closeDelete}>
              {t("cancel")}
            </Button>
            <Button color="red" loading={saving} onClick={() => void handleDelete()}>
              {t("delete")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
