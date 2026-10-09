import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { AppPage } from "../../components/AppPage/AppPage";
import {
  Badge,
  Box,
  Button,
  Card,
  Drawer,
  Group,
  Loader,
  Modal,
  NativeSelect,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconPlus } from "@tabler/icons-react";
import {
  createPldEntity,
  deletePldEntity,
  getPldEntityProgress,
  listPldEntities,
  sendPldEntityInvite,
  startPldProcess,
  TPldEntity,
  TPldEntityProgress,
} from "../../modules/apiCalls";

const CLOSED = new Set(["signed", "delivered"]);
const HIGH_RISK = new Set(["orange", "red"]);
const STAGES = [
  "data_collection",
  "document_collection",
  "cross_reference",
  "waiting_sign",
  "signed",
  "delivered",
  "action_required",
];

function entityDisplayName(entity: TPldEntity): string {
  const meta = entity.metadata || {};
  const name = meta.legal_name || meta.name;
  return typeof name === "string" && name.trim() ? name.trim() : entity.id;
}

function riskBadgeColor(semaphore?: string) {
  if (semaphore === "green") return "teal";
  if (semaphore === "yellow") return "yellow";
  if (semaphore === "orange") return "orange";
  if (semaphore === "red") return "red";
  return "gray";
}

function stepBadgeColor(state: string) {
  if (state === "done") return "teal";
  if (state === "current") return "violet";
  return "gray";
}

export default function ComplianceHubPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [entities, setEntities] = useState<TPldEntity[]>([]);
  const [orgProcessReady, setOrgProcessReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [invitingId, setInvitingId] = useState<string | null>(null);
  const [addOpened, { open: openAdd, close: closeAdd }] = useDisclosure(false);
  const [deleteOpened, { open: openDelete, close: closeDelete }] =
    useDisclosure(false);
  const [pendingDelete, setPendingDelete] = useState<TPldEntity | null>(null);
  const [personType, setPersonType] = useState("persona_moral");
  const [relationship, setRelationship] = useState("cliente");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [ppeEnabled, setPpeEnabled] = useState(false);
  const [query, setQuery] = useState("");
  const [relFilter, setRelFilter] = useState("all");
  const [stageFilter, setStageFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [panelOpened, { open: openPanel, close: closePanel }] = useDisclosure(false);
  const [selected, setSelected] = useState<TPldEntity | null>(null);
  const [progress, setProgress] = useState<TPldEntityProgress | null>(null);
  const [progressLoading, setProgressLoading] = useState(false);

  const loadEntities = async () => {
    try {
      const data = await listPldEntities();
      const rows = data.results || [];
      setEntities(rows);
      setSelected((current) => {
        if (!current) return current;
        return rows.find((row) => row.id === current.id) || current;
      });
      setOrgProcessReady(Boolean(data.org_process_ready));
    } catch {
      toast.error(t("compliance-entities-load-error"));
      setEntities([]);
      setOrgProcessReady(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadEntities();
  }, []);

  const resetAddForm = () => {
    setDisplayName("");
    setEmail("");
    setPersonType("persona_moral");
    setRelationship("cliente");
    setPpeEnabled(false);
  };

  const handleCreate = async () => {
    const name = displayName.trim();
    const inviteEmail = email.trim();
    if (!name) {
      toast.error(t("compliance-counterparty-name-required"));
      return;
    }
    if (!inviteEmail) {
      toast.error(t("compliance-counterparty-email-required"));
      return;
    }
    setSaving(true);
    try {
      await createPldEntity({
        person_type: personType,
        relationship,
        email: inviteEmail,
        ppe_screening_enabled: ppeEnabled,
        metadata:
          personType === "persona_moral"
            ? { legal_name: name }
            : { name },
      });
      closeAdd();
      resetAddForm();
      toast.success(t("compliance-counterparty-created"));
      setLoading(true);
      await loadEntities();
    } catch {
      toast.error(t("compliance-counterparty-create-error"));
    } finally {
      setSaving(false);
    }
  };

  const handleInvite = async (entity: TPldEntity) => {
    setInvitingId(entity.id);
    try {
      await sendPldEntityInvite(entity.id);
      toast.success(t("compliance-invite-sent"));
      await loadEntities();
    } catch {
      toast.error(t("compliance-invite-send-error"));
    } finally {
      setInvitingId(null);
    }
  };

  const handleDelete = async () => {
    if (!pendingDelete) return;
    try {
      await deletePldEntity(pendingDelete.id);
      toast.success(t("compliance-counterparty-deleted"));
      closeDelete();
      closePanel();
      setSelected(null);
      setPendingDelete(null);
      await loadEntities();
    } catch {
      toast.error(t("compliance-counterparty-delete-error"));
    }
  };

  const handleStartProcess = async () => {
    setStarting(true);
    try {
      await startPldProcess();
      navigate("/pld/expediente");
    } catch {
      toast.error(t("compliance-start-process-error"));
    } finally {
      setStarting(false);
    }
  };

  const inviteLabel = (entity: TPldEntity) => {
    if (entity.invite?.status === "accepted") return t("compliance-invite-accepted");
    if (entity.invite?.status === "pending") return t("compliance-invite-pending");
    return t("compliance-invite-none");
  };

  const openRow = async (entity: TPldEntity) => {
    setSelected(entity);
    setProgress(null);
    openPanel();
    setProgressLoading(true);
    try {
      setProgress(await getPldEntityProgress(entity.id));
    } catch {
      toast.error(t("compliance-progress-error"));
    } finally {
      setProgressLoading(false);
    }
  };

  const ordered = [...entities].sort((a, b) => {
    if (a.relationship == null) return -1;
    if (b.relationship == null) return 1;
    return 0;
  });
  const needle = query.trim().toLowerCase();
  const visible = ordered.filter((entity) => {
    if (needle) {
      const blob = [
        entityDisplayName(entity),
        entity.email || "",
        entity.rfc || "",
      ]
        .join(" ")
        .toLowerCase();
      if (!blob.includes(needle)) return false;
    }
    if (relFilter === "self" && entity.relationship != null) return false;
    if (relFilter !== "all" && relFilter !== "self" && entity.relationship !== relFilter) {
      return false;
    }
    if (stageFilter !== "all" && entity.expedient?.status !== stageFilter) return false;
    const semaphore = entity.expedient?.semaphore || "";
    if (riskFilter === "none" && semaphore) return false;
    if (riskFilter !== "all" && riskFilter !== "none" && semaphore !== riskFilter) {
      return false;
    }
    return true;
  });
  const openCount = entities.filter((entity) => !CLOSED.has(entity.expedient?.status || "")).length;
  const actionCount = entities.filter(
    (entity) => entity.expedient?.status === "action_required"
  ).length;
  const highRiskCount = entities.filter((entity) =>
    HIGH_RISK.has(entity.expedient?.semaphore || "")
  ).length;

  return (
    <AppPage title={t("compliance-hub-title")}>
        <Box w="100%" maw="80rem" mx="auto">
          <Text c="dimmed" mb="lg" size="sm">
            {t("compliance-hub-description")}
          </Text>

          <SimpleGrid cols={{ base: 2, sm: 4 }} mb="lg">
            <Card withBorder p="md">
              <Text size="xl" fw={600}>{entities.length}</Text>
              <Text size="sm" c="dimmed">{t("compliance-count-files")}</Text>
            </Card>
            <Card withBorder p="md">
              <Text size="xl" fw={600}>{openCount}</Text>
              <Text size="sm" c="dimmed">{t("compliance-count-open")}</Text>
            </Card>
            <Card withBorder p="md">
              <Text size="xl" fw={600}>{actionCount}</Text>
              <Text size="sm" c="dimmed">{t("compliance-count-action")}</Text>
            </Card>
            <Card withBorder p="md">
              <Text size="xl" fw={600}>{highRiskCount}</Text>
              <Text size="sm" c="dimmed">{t("compliance-count-high-risk")}</Text>
            </Card>
          </SimpleGrid>

          <Card withBorder p="lg" mb="lg">
            <Group justify="space-between" align="flex-start" wrap="wrap">
              <Text size="sm" c="dimmed" style={{ flex: 1, minWidth: 0 }}>
                {orgProcessReady
                  ? t("compliance-start-process-ready")
                  : t("compliance-start-process-blocked")}
              </Text>
              <Button
                disabled={!orgProcessReady}
                loading={starting}
                onClick={() => void handleStartProcess()}
              >
                {t("compliance-start-process")}
              </Button>
            </Group>
          </Card>

          <Card withBorder p="lg">
            <Group justify="space-between" mb="md">
              <Title order={4}>{t("compliance-counterparties")}</Title>
              <Button
                size="xs"
                leftSection={<IconPlus size={14} />}
                onClick={openAdd}
              >
                {t("compliance-add-counterparty")}
              </Button>
            </Group>

            <Group mb="md" grow align="flex-end">
              <TextInput
                placeholder={t("compliance-search")}
                value={query}
                onChange={(e) => {
                  const val = e.currentTarget.value;
                  setQuery(val);
                }}
              />
              <NativeSelect
                aria-label={t("compliance-filter-relationship")}
                value={relFilter}
                onChange={(e) => {
                  const val = e.currentTarget.value;
                  setRelFilter(val);
                }}
                data={[
                  { value: "all", label: t("compliance-filter-all") },
                  { value: "self", label: t("compliance-self-entity") },
                  { value: "cliente", label: t("compliance-rel-cliente") },
                  { value: "proveedor", label: t("compliance-rel-proveedor") },
                  { value: "ambos", label: t("compliance-rel-ambos") },
                ]}
              />
              <NativeSelect
                aria-label={t("compliance-filter-stage")}
                value={stageFilter}
                onChange={(e) => {
                  const val = e.currentTarget.value;
                  setStageFilter(val);
                }}
                data={[
                  { value: "all", label: t("compliance-filter-all") },
                  ...STAGES.map((status) => ({
                    value: status,
                    label: t(`compliance-status-${status}`),
                  })),
                ]}
              />
              <NativeSelect
                aria-label={t("compliance-filter-risk")}
                value={riskFilter}
                onChange={(e) => {
                  const val = e.currentTarget.value;
                  setRiskFilter(val);
                }}
                data={[
                  { value: "all", label: t("compliance-filter-all") },
                  { value: "green", label: t("compliance-risk-green") },
                  { value: "yellow", label: t("compliance-risk-yellow") },
                  { value: "orange", label: t("compliance-risk-orange") },
                  { value: "red", label: t("compliance-risk-red") },
                  { value: "none", label: t("compliance-risk-none") },
                ]}
              />
            </Group>

            {loading ? (
              <Stack align="center" py="xl">
                <Loader color="violet" size="sm" />
              </Stack>
            ) : entities.length === 0 ? (
              <Text c="dimmed" ta="center" py="xl">
                {t("compliance-no-counterparties")}
              </Text>
            ) : visible.length === 0 ? (
              <Text c="dimmed" ta="center" py="xl">
                {t("compliance-no-matches")}
              </Text>
            ) : (
              <Table.ScrollContainer minWidth={720}>
                <Table highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t("compliance-col-name")}</Table.Th>
                      <Table.Th>{t("compliance-col-rfc")}</Table.Th>
                      <Table.Th>{t("compliance-col-type")}</Table.Th>
                      <Table.Th>{t("compliance-col-stage")}</Table.Th>
                      <Table.Th>{t("compliance-col-risk")}</Table.Th>
                      <Table.Th>{t("compliance-col-invite")}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {visible.map((entity) => (
                      <Table.Tr
                        key={entity.id}
                        style={{ cursor: "pointer" }}
                        onClick={() => void openRow(entity)}
                      >
                        <Table.Td>
                          <Text fw={500}>{entityDisplayName(entity)}</Text>
                          <Text size="xs" c="dimmed">
                            {t(`compliance-person-${entity.person_type}`)}
                          </Text>
                        </Table.Td>
                        <Table.Td>{entity.rfc || "—"}</Table.Td>
                        <Table.Td>
                          {entity.relationship
                            ? t(`compliance-rel-${entity.relationship}`)
                            : t("compliance-self-entity")}
                        </Table.Td>
                        <Table.Td>
                          {entity.expedient
                            ? t(`compliance-status-${entity.expedient.status}`, {
                                defaultValue: entity.expedient.status,
                              })
                            : "—"}
                        </Table.Td>
                        <Table.Td>
                          {entity.expedient?.semaphore ? (
                            <Badge
                              variant="light"
                              color={riskBadgeColor(entity.expedient.semaphore)}
                            >
                              {t(`compliance-risk-${entity.expedient.semaphore}`, {
                                defaultValue: entity.expedient.semaphore,
                              })}
                            </Badge>
                          ) : (
                            "—"
                          )}
                        </Table.Td>
                        <Table.Td>
                          {entity.relationship ? inviteLabel(entity) : "—"}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}
          </Card>
        </Box>

        <Drawer
          opened={panelOpened}
          onClose={closePanel}
          position="right"
          title={selected ? entityDisplayName(selected) : ""}
          size="md"
        >
          {selected && (
            <Stack gap="md">
              <Text size="sm" c="dimmed">
                {selected.relationship
                  ? t(`compliance-rel-${selected.relationship}`)
                  : t("compliance-self-entity")}
                {selected.email ? ` · ${selected.email}` : ""}
              </Text>
              {progressLoading ? (
                <Stack align="center" py="xl">
                  <Loader color="violet" size="sm" />
                </Stack>
              ) : progress ? (
                <Stack gap="sm">
                  {progress.steps.map((step) => (
                    <Group key={step.id} justify="space-between">
                      <Text size="sm">{t(`compliance-step-${step.id}`)}</Text>
                      <Badge variant="light" color={stepBadgeColor(step.state)}>
                        {t(`compliance-step-${step.state}`)}
                      </Badge>
                    </Group>
                  ))}
                  <Text size="sm">
                    {t("compliance-documents-progress", {
                      filled: progress.documents.filled,
                      required: progress.documents.required,
                    })}
                  </Text>
                  <Text size="sm">
                    {t("compliance-list-hits", { hits: progress.screening_hit_count })}
                  </Text>
                  <Text size="sm">
                    {t("compliance-ppe-hits", { hits: progress.ppe_hit_count })}
                  </Text>
                  {progress.matrix ? (
                    <Group gap="xs">
                      <Text size="sm">
                        {t("compliance-matrix-score", { score: progress.matrix.total })}
                      </Text>
                      <Badge variant="light" color={riskBadgeColor(progress.matrix.color)}>
                        {t(`compliance-risk-${progress.matrix.color}`, {
                          defaultValue: progress.matrix.color,
                        })}
                      </Badge>
                    </Group>
                  ) : null}
                  <Text size="sm">
                    {progress.signature.status === "signed"
                      ? t("compliance-signature-signed")
                      : progress.signature.status === "waiting"
                        ? t("compliance-signature-waiting")
                        : t("compliance-signature-none")}
                  </Text>
                  {progress.recommended_action ? (
                    <Text size="sm">
                      {t("compliance-recommended-action")}:{" "}
                      {t(`compliance-action-${progress.recommended_action}`, {
                        defaultValue: progress.recommended_action,
                      })}
                    </Text>
                  ) : null}
                  {progress.reasons.length > 0 ? (
                    <Stack gap={4}>
                      <Text size="sm" fw={500}>{t("compliance-reasons")}</Text>
                      {progress.reasons.map((reason) => (
                        <Text key={reason} size="sm" c="dimmed">
                          {t(`compliance-reason-${reason}`, { defaultValue: reason })}
                        </Text>
                      ))}
                    </Stack>
                  ) : null}
                </Stack>
              ) : null}
              {selected.relationship ? (
                <Group>
                  <Button
                    variant="default"
                    loading={invitingId === selected.id}
                    onClick={() => void handleInvite(selected)}
                  >
                    {selected.invite?.status === "pending"
                      ? t("compliance-invite-resend")
                      : t("compliance-invite-send")}
                  </Button>
                  <Button
                    color="red"
                    variant="light"
                    onClick={() => {
                      setPendingDelete(selected);
                      openDelete();
                    }}
                  >
                    {t("delete")}
                  </Button>
                </Group>
              ) : null}
            </Stack>
          )}
        </Drawer>

      <Modal
        opened={addOpened}
        onClose={closeAdd}
        title={t("compliance-add-counterparty")}
        centered
      >
        <Stack gap="md">
          <NativeSelect
            label={t("compliance-person-type")}
            value={personType}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setPersonType(val);
            }}
            data={[
              {
                value: "persona_moral",
                label: t("compliance-person-persona_moral"),
              },
              {
                value: "persona_fisica",
                label: t("compliance-person-persona_fisica"),
              },
            ]}
          />
          <NativeSelect
            label={t("compliance-relationship")}
            value={relationship}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setRelationship(val);
            }}
            data={[
              { value: "cliente", label: t("compliance-rel-cliente") },
              { value: "proveedor", label: t("compliance-rel-proveedor") },
              { value: "ambos", label: t("compliance-rel-ambos") },
            ]}
          />
          <TextInput
            label={t("name")}
            value={displayName}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setDisplayName(val);
            }}
          />
          <TextInput
            label={t("email")}
            type="email"
            value={email}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setEmail(val);
            }}
          />
          <Switch
            label={t("compliance-ppe-toggle")}
            description={t("compliance-ppe-toggle-help")}
            checked={ppeEnabled}
            onChange={(e) => setPpeEnabled(e.currentTarget.checked)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={closeAdd} disabled={saving}>
              {t("cancel")}
            </Button>
            <Button onClick={handleCreate} loading={saving}>
              {t("compliance-add-counterparty")}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={deleteOpened}
        onClose={() => {
          closeDelete();
          setPendingDelete(null);
        }}
        title={t("compliance-delete-counterparty-title")}
        centered
      >
        <Stack gap="md">
          <Text size="sm">
            {t("compliance-delete-counterparty-description", {
              name: pendingDelete ? entityDisplayName(pendingDelete) : "",
            })}
          </Text>
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => {
                closeDelete();
                setPendingDelete(null);
              }}
            >
              {t("cancel")}
            </Button>
            <Button color="red" onClick={() => void handleDelete()}>
              {t("delete")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </AppPage>
  );
}
