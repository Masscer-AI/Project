import React, { useEffect, useState } from "react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import "./page.css";
import {
  getWhatsappNumbers,
  getWhatsappContacts,
  updateWhatsappContact,
  getOrganizationMembers,
  updateWhatsappNumber,
  TWhatsappContact,
} from "../../modules/apiCalls";
import { AgentSelector } from "../../components/AgentSelector/AgentSelector";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useDisclosure } from "@mantine/hooks";
import { useNavigate } from "react-router-dom";

import {
  ActionIcon,
  Box,
  Button,
  Card,
  Checkbox,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconMenu2, IconDeviceFloppy, IconUsers } from "@tabler/icons-react";
import { TOrganizationMember } from "../../types";

/** Tools that make sense on WhatsApp (no plugins / doc templates — web UI only). */
const WHATSAPP_CAPABILITY_NAMES = [
  "read_attachment",
  "list_attachments",
  "explore_web",
  "rag_query",
  "create_image",
  "create_speech",
  "generate_dialogue",
  "generate_video",
  "generate_document_file",
] as const;

const WHATSAPP_REQUIRED_CAPABILITY_NAMES = [
  "read_attachment",
  "list_attachments",
] as const;
const WHATSAPP_REQUIRED_CAPABILITY_SET = new Set<string>(
  WHATSAPP_REQUIRED_CAPABILITY_NAMES
);

function buildInitialCapabilityState(
  capabilities: { name?: string; type?: string; enabled?: boolean }[] | null | undefined
): Record<string, boolean> {
  const initial: Record<string, boolean> = {};
  for (const n of WHATSAPP_CAPABILITY_NAMES) initial[n] = false;
  for (const c of capabilities ?? []) {
    if (c?.name) initial[c.name] = Boolean(c.enabled);
  }
  for (const requiredName of WHATSAPP_REQUIRED_CAPABILITY_NAMES) {
    initial[requiredName] = true;
  }
  return initial;
}

function buildCapabilitiesPayload(
  capabilityState: Record<string, boolean>
): { name: string; type: "internal_tool"; enabled: boolean }[] {
  return WHATSAPP_CAPABILITY_NAMES.map((name) => ({
    name,
    type: "internal_tool",
    enabled: capabilityState[name] ?? false,
  }));
}

type WhatsappLine = {
  id: number;
  number: string;
  agent: { name: string; slug: string };
  conversations_count: number;
  name: string | null;
  organization?: number | string | null;
  capabilities?: { name?: string; type?: string; enabled?: boolean }[] | null;
};

export default function Whatsapp() {
  const { t } = useTranslation();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const [numbers, setNumbers] = useState<WhatsappLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refreshNumbers = () => {
    return getWhatsappNumbers()
      .then((res) => {
        setNumbers(res as WhatsappLine[]);
        setLoadError(null);
      })
      .catch(() => {
        setLoadError(t("whatsapp-load-error"));
      });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getWhatsappNumbers()
      .then((res) => {
        if (!cancelled) {
          setNumbers(res as WhatsappLine[]);
          setLoadError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(t("whatsapp-load-error"));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

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

        <Box px="md" w="100%" maw="42rem" mx="auto">
          <Title order={2} ta="center" mb="lg" mt="md">
            {t("whatsapp")}
          </Title>
          <Text mb="md">{t("whatsapp-intro")}</Text>
          <Text size="sm" c="dimmed" mb="md">
            {t("whatsapp-provision-note")}
          </Text>

          <Title order={4} mb="sm">
            {t("whatsapp-your-numbers")}
          </Title>

          {loading ? (
            <Stack align="center" py="xl">
              <Loader color="violet" />
            </Stack>
          ) : loadError ? (
            <Text c="red">{loadError}</Text>
          ) : numbers.length === 0 ? (
            <Text c="dimmed">{t("whatsapp-empty-lines")}</Text>
          ) : (
            <Stack gap="md">
              {numbers.map((line) => (
                <WhatsAppNumber
                  key={line.id}
                  line={line}
                  onRefresh={refreshNumbers}
                />
              ))}
            </Stack>
          )}
        </Box>
      </div>
    </main>
  );
}

const WhatsAppNumber = ({
  line,
  onRefresh,
}: {
  line: WhatsappLine;
  onRefresh: () => Promise<void>;
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { number, agent, conversations_count, name } = line;
  const [settingsOpened, { open: openSettings, close: closeSettings }] =
    useDisclosure(false);
  const [contactsOpened, { open: openContacts, close: closeContacts }] =
    useDisclosure(false);
  const [nameInput, setNameInput] = useState(name ?? "");
  const [capabilityState, setCapabilityState] = useState<Record<string, boolean>>(
    () => buildInitialCapabilityState(line.capabilities)
  );
  const [contacts, setContacts] = useState<TWhatsappContact[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [contactsError, setContactsError] = useState<string | null>(null);
  const [members, setMembers] = useState<TOrganizationMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [linkSelection, setLinkSelection] = useState<Record<number, string>>({});
  const [linkingId, setLinkingId] = useState<number | null>(null);

  useEffect(() => {
    if (!settingsOpened) return;
    setNameInput(line.name ?? "");
    setCapabilityState(buildInitialCapabilityState(line.capabilities));
  }, [settingsOpened, line.name, line.capabilities, line.number]);

  useEffect(() => {
    if (!contactsOpened) return;
    let cancelled = false;
    setContactsLoading(true);
    setContactsError(null);
    getWhatsappContacts(line.id)
      .then((res) => {
        if (!cancelled) setContacts(res);
      })
      .catch(() => {
        if (!cancelled) setContactsError(t("whatsapp-contacts-load-error"));
      })
      .finally(() => {
        if (!cancelled) setContactsLoading(false);
      });

    const orgId = line.organization;
    if (orgId != null && orgId !== "") {
      setMembersLoading(true);
      getOrganizationMembers(String(orgId))
        .then((res) => {
          if (!cancelled) setMembers(res.filter((m) => m.is_active || m.is_owner));
        })
        .catch(() => {
          if (!cancelled) setMembers([]);
        })
        .finally(() => {
          if (!cancelled) setMembersLoading(false);
        });
    } else {
      setMembers([]);
    }

    return () => {
      cancelled = true;
    };
  }, [contactsOpened, line.id, line.organization, t]);

  const changeAgent = (slug: string) => {
    updateWhatsappNumber(number, { slug }).then(() => {
      toast.success(t("whatsapp-agent-changed"));
      void onRefresh();
    });
  };

  const updateName = () => {
    updateWhatsappNumber(number, { name: nameInput }).then(() => {
      toast.success(t("whatsapp-name-updated"));
      void onRefresh();
    });
  };

  const saveCapabilities = () => {
    const capabilities = buildCapabilitiesPayload(capabilityState);
    updateWhatsappNumber(number, { capabilities }).then(() => {
      toast.success(t("whatsapp-capabilities-saved"));
      void onRefresh();
    });
  };

  const linkContact = async (contact: TWhatsappContact) => {
    const selected = linkSelection[contact.id];
    if (!selected) return;
    setLinkingId(contact.id);
    try {
      const updated = await updateWhatsappContact(contact.id, {
        user_id: Number(selected),
      });
      setContacts((prev) =>
        prev.map((c) => (c.id === contact.id ? updated : c))
      );
      toast.success(t("whatsapp-contact-linked"));
    } catch {
      toast.error(t("whatsapp-contact-link-error"));
    } finally {
      setLinkingId(null);
    }
  };

  const unlinkContact = async (contact: TWhatsappContact) => {
    setLinkingId(contact.id);
    try {
      const updated = await updateWhatsappContact(contact.id, { user_id: null });
      setContacts((prev) =>
        prev.map((c) => (c.id === contact.id ? updated : c))
      );
      toast.success(t("whatsapp-contact-unlinked-toast"));
    } catch {
      toast.error(t("whatsapp-contact-link-error"));
    } finally {
      setLinkingId(null);
    }
  };

  return (
    <>
      <Card
        withBorder
        padding="lg"
        style={{ cursor: "pointer" }}
        onClick={openSettings}
      >
        <Title order={4} ta="center">
          {name || number}
        </Title>
        <Text ta="center" size="lg">
          📞 {number}
        </Text>
        <Group justify="center" gap="md" mt="xs">
          <Text size="sm">🧠 {agent.name}</Text>
          <Text size="sm">💬 {conversations_count}</Text>
        </Group>
        <Group justify="center" mt="sm" onClick={(e) => e.stopPropagation()}>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconUsers size={14} />}
            onClick={openContacts}
          >
            {t("whatsapp-contacts")}
          </Button>
          <Button
            size="xs"
            variant="light"
            onClick={() => navigate(`/dashboard?wsNumberId=${line.id}&channel=whatsapp`)}
          >
            {t("view-conversations")}
          </Button>
        </Group>
      </Card>

      <Modal
        opened={contactsOpened}
        onClose={closeContacts}
        title={t("whatsapp-contacts-title")}
        centered
        size="lg"
      >
        {contactsLoading ? (
          <Stack align="center" py="md">
            <Loader color="violet" size="sm" />
          </Stack>
        ) : contactsError ? (
          <Text c="red">{contactsError}</Text>
        ) : contacts.length === 0 ? (
          <Text c="dimmed">{t("whatsapp-contacts-empty")}</Text>
        ) : (
          <Stack gap="sm">
            {contacts.map((contact) => {
              const memberLabel =
                contact.user_display_name ||
                contact.user_email ||
                (contact.user_id != null ? `#${contact.user_id}` : null);
              return (
                <Card key={contact.id} withBorder padding="sm">
                  <Group justify="space-between" align="flex-start" wrap="wrap">
                    <Stack gap={2}>
                      <Text size="sm" fw={500}>
                        {t("whatsapp-contact-phone")}: +{contact.number}
                      </Text>
                      {contact.display_name ? (
                        <Text size="xs" c="dimmed">
                          {contact.display_name}
                        </Text>
                      ) : null}
                      <Text size="sm">
                        {t("whatsapp-contact-member")}:{" "}
                        {memberLabel || t("whatsapp-contact-unlinked")}
                      </Text>
                    </Stack>
                    <Stack gap="xs" style={{ minWidth: 180 }}>
                      {contact.user_id != null ? (
                        <Button
                          size="xs"
                          variant="default"
                          loading={linkingId === contact.id}
                          onClick={() => void unlinkContact(contact)}
                        >
                          {t("whatsapp-contact-unlink")}
                        </Button>
                      ) : (
                        <>
                          <NativeSelect
                            size="xs"
                            data={[
                              {
                                value: "",
                                label: t("whatsapp-contact-select-member"),
                              },
                              ...members.map((m) => ({
                                value: String(m.id),
                                label:
                                  m.profile_name ||
                                  m.email ||
                                  m.username ||
                                  String(m.id),
                              })),
                            ]}
                            value={linkSelection[contact.id] ?? ""}
                            onChange={(e) => {
                              const val = e.currentTarget.value;
                              setLinkSelection((prev) => ({
                                ...prev,
                                [contact.id]: val,
                              }));
                            }}
                            disabled={membersLoading || members.length === 0}
                          />
                          <Button
                            size="xs"
                            loading={linkingId === contact.id}
                            disabled={!linkSelection[contact.id]}
                            onClick={() => void linkContact(contact)}
                          >
                            {t("whatsapp-contact-link")}
                          </Button>
                        </>
                      )}
                    </Stack>
                  </Group>
                </Card>
              );
            })}
          </Stack>
        )}
      </Modal>

      <Modal
        opened={settingsOpened}
        onClose={closeSettings}
        title={t("whatsapp-settings-title")}
        centered
        size="lg"
      >
        <Stack gap="md">
          <Group gap="sm" align="flex-end">
            <TextInput
              label={t("whatsapp-display-name")}
              value={nameInput}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setNameInput(val);
              }}
              style={{ flex: 1 }}
            />
            <Button
              leftSection={<IconDeviceFloppy size={16} />}
              onClick={updateName}
            >
              {t("whatsapp-update-name")}
            </Button>
          </Group>

          <div>
            <Text size="sm" fw={500} mb={4}>
              {t("whatsapp-change-agent")}
            </Text>
            <AgentSelector
              onSelectAgent={changeAgent}
              selectedSlug={agent.slug}
            />
          </div>

          <div>
            <Text size="sm" fw={500} mb="xs">
              {t("whatsapp-capabilities")}
            </Text>
            <Stack gap="sm">
              {WHATSAPP_CAPABILITY_NAMES.map((capName) => (
                <Stack key={capName} gap={2}>
                  {(() => {
                    const isRequired = WHATSAPP_REQUIRED_CAPABILITY_SET.has(capName);
                    return (
                  <Checkbox
                    label={t(`widget-capability-${capName}-title`)}
                    checked={capabilityState[capName] ?? false}
                    disabled={isRequired}
                    onChange={(e) => {
                      if (isRequired) return;
                      const checked = e.currentTarget.checked;
                      setCapabilityState((prev) => ({
                        ...prev,
                        [capName]: checked,
                      }));
                    }}
                  />
                    );
                  })()}
                  <Text size="xs" c="dimmed" ml={28}>
                    {t(`widget-capability-${capName}-description`)}
                  </Text>
                </Stack>
              ))}
            </Stack>
            <Button
              mt="sm"
              leftSection={<IconDeviceFloppy size={16} />}
              variant="default"
              onClick={saveCapabilities}
            >
              {t("whatsapp-save-capabilities")}
            </Button>
          </div>

          <Button
            variant="light"
            fullWidth
            onClick={() => {
              closeSettings();
              navigate(`/dashboard?wsNumberId=${line.id}&channel=whatsapp`);
            }}
          >
            {t("view-conversations")}
          </Button>
        </Stack>
      </Modal>
    </>
  );
};

