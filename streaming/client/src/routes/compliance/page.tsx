import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconMail,
  IconMenu2,
  IconPlus,
  IconScale,
  IconTrash,
} from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import {
  createPldEntity,
  deletePldEntity,
  listPldEntities,
  sendPldEntityInvite,
  TPldEntity,
} from "../../modules/apiCalls";

function entityDisplayName(entity: TPldEntity): string {
  const meta = entity.metadata || {};
  const name = meta.legal_name || meta.name;
  return typeof name === "string" && name.trim() ? name.trim() : entity.id;
}

export default function ComplianceHubPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));
  const [entities, setEntities] = useState<TPldEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [invitingId, setInvitingId] = useState<string | null>(null);
  const [addOpened, { open: openAdd, close: closeAdd }] = useDisclosure(false);
  const [deleteOpened, { open: openDelete, close: closeDelete }] =
    useDisclosure(false);
  const [pendingDelete, setPendingDelete] = useState<TPldEntity | null>(null);
  const [personType, setPersonType] = useState("persona_moral");
  const [relationship, setRelationship] = useState("cliente");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");

  const loadEntities = async () => {
    try {
      const data = await listPldEntities();
      setEntities(data.results || []);
    } catch {
      toast.error(t("compliance-entities-load-error"));
      setEntities([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadEntities();
  }, []);

  const counterparties = entities.filter((e) => e.relationship != null);
  const selfEntity = entities.find((e) => e.relationship == null);

  const resetAddForm = () => {
    setDisplayName("");
    setEmail("");
    setPersonType("persona_moral");
    setRelationship("cliente");
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
      setPendingDelete(null);
      await loadEntities();
    } catch {
      toast.error(t("compliance-counterparty-delete-error"));
    }
  };

  const inviteLabel = (entity: TPldEntity) => {
    if (entity.invite?.status === "accepted") return t("compliance-invite-accepted");
    if (entity.invite?.status === "pending") return t("compliance-invite-resend");
    return t("compliance-invite-send");
  };

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          padding: 24,
          overflowY: "auto",
          minHeight: "100vh",
          display: "flex",
          justifyContent: "center",
        }}
        className="relative"
      >
        {!chatState.isSidebarOpened && (
          <Box pos="absolute" top={24} left={24} style={{ zIndex: 10 }}>
            <ActionIcon variant="subtle" color="gray" onClick={toggleSidebar}>
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box px="md" w="100%" maw="52rem" mx="auto">
          <Title order={2} ta="center" mb="xs" mt="md">
            {t("compliance-hub-title")}
          </Title>
          <Text ta="center" c="dimmed" mb="lg" size="sm">
            {t("compliance-hub-description")}
          </Text>

          <Card withBorder p="lg" mb="lg">
            <Group justify="space-between" align="flex-start" wrap="wrap">
              <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
                <Text fw={600}>{t("compliance-assistant-card-title")}</Text>
                <Text size="sm" c="dimmed">
                  {t("compliance-assistant-card-description")}
                </Text>
              </Stack>
              <Button
                leftSection={<IconScale size={16} />}
                onClick={() => navigate("/compliance/chat")}
              >
                {t("compliance-open-assistant")}
              </Button>
            </Group>
          </Card>

          {selfEntity && (
            <Card withBorder p="md" mb="lg">
              <Group justify="space-between">
                <Stack gap={2}>
                  <Text fw={500}>{entityDisplayName(selfEntity)}</Text>
                  <Text size="sm" c="dimmed">
                    {t("compliance-self-entity")}
                  </Text>
                </Stack>
                {selfEntity.expedient && (
                  <Badge variant="light" color="violet">
                    {t(`compliance-status-${selfEntity.expedient.status}`, {
                      defaultValue: selfEntity.expedient.status,
                    })}
                  </Badge>
                )}
              </Group>
            </Card>
          )}

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

            {loading ? (
              <Stack align="center" py="xl">
                <Loader color="violet" size="sm" />
              </Stack>
            ) : counterparties.length === 0 ? (
              <Text c="dimmed" ta="center" py="xl">
                {t("compliance-no-counterparties")}
              </Text>
            ) : (
              <Stack gap="sm">
                {counterparties.map((entity) => (
                  <Card
                    key={entity.id}
                    withBorder
                    p="sm"
                    style={{ background: "rgba(255,255,255,0.02)" }}
                  >
                    <Group justify="space-between" wrap="nowrap" align="flex-start">
                      <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
                        <Text fw={500} truncate>
                          {entityDisplayName(entity)}
                        </Text>
                        <Text size="sm" c="dimmed">
                          {t(`compliance-person-${entity.person_type}`)} ·{" "}
                          {t(`compliance-rel-${entity.relationship}`)}
                        </Text>
                        {entity.email && (
                          <Text size="sm" c="dimmed" truncate>
                            {entity.email}
                          </Text>
                        )}
                      </Stack>
                      <Group gap="xs" wrap="nowrap">
                        {entity.expedient && (
                          <Badge variant="outline" color="gray">
                            {t(`compliance-status-${entity.expedient.status}`, {
                              defaultValue: entity.expedient.status,
                            })}
                          </Badge>
                        )}
                        <Tooltip label={inviteLabel(entity)}>
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            aria-label={inviteLabel(entity)}
                            loading={invitingId === entity.id}
                            onClick={() => void handleInvite(entity)}
                          >
                            <IconMail size={16} />
                          </ActionIcon>
                        </Tooltip>
                        <Tooltip label={t("delete")}>
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            aria-label={t("delete")}
                            onClick={() => {
                              setPendingDelete(entity);
                              openDelete();
                            }}
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    </Group>
                  </Card>
                ))}
              </Stack>
            )}
          </Card>
        </Box>
      </div>

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
    </main>
  );
}
