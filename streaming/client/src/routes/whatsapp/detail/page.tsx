import React, { useEffect, useMemo, useState } from "react";
import { Sidebar } from "../../../components/Sidebar/Sidebar";
import { useStore } from "../../../modules/store";
import "../page.css";
import {
  getWhatsappNumbers,
  getWhatsappContacts,
  updateWhatsappContact,
  getOrganizationMembers,
  getOrganizationRoles,
  updateWhatsappNumber,
  TWhatsappContact,
} from "../../../modules/apiCalls";
import { AgentSelector } from "../../../components/AgentSelector/AgentSelector";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  ActionIcon,
  Box,
  Button,
  Card,
  Group,
  Loader,
  MultiSelect,
  NativeSelect,
  Stack,
  Tabs,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconDeviceFloppy,
  IconMenu2,
  IconMessages,
  IconSettings,
  IconUsers,
} from "@tabler/icons-react";
import { TOrganizationMember, TOrganizationRole } from "../../../types";
import { CapabilitiesChecklist } from "../../../components/CapabilitiesChecklist/CapabilitiesChecklist";
import {
  WHATSAPP_CAPABILITY_NAMES,
  WHATSAPP_REQUIRED_CAPABILITY_NAMES,
  WhatsappAccessMode,
  WhatsappLine,
  buildCapabilitiesPayload,
  buildInitialCapabilityState,
} from "../shared";

type DetailTab = "contacts" | "settings";

function isDetailTab(value: string | null): value is DetailTab {
  return value === "contacts" || value === "settings";
}

export default function WhatsappLineDetail() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { wsNumberId } = useParams<{ wsNumberId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { chatState, toggleSidebar, agents, fetchAgents } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));

  const [line, setLine] = useState<WhatsappLine | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (agents.length === 0) {
      void fetchAgents();
    }
  }, [agents.length, fetchAgents]);

  const activeTab: DetailTab = isDetailTab(searchParams.get("tab"))
    ? (searchParams.get("tab") as DetailTab)
    : "contacts";

  const setActiveTab = (value: string | null) => {
    const tab: DetailTab = isDetailTab(value) ? value : "contacts";
    setSearchParams(tab === "contacts" ? {} : { tab }, { replace: true });
  };

  const refreshLine = async () => {
    const res = (await getWhatsappNumbers()) as WhatsappLine[];
    const id = Number(wsNumberId);
    const found = res.find((n) => n.id === id) ?? null;
    setLine(found);
    if (!found) {
      setLoadError(t("whatsapp-line-not-found"));
    } else {
      setLoadError(null);
    }
    return found;
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    refreshLine()
      .catch(() => {
        if (!cancelled) setLoadError(t("whatsapp-load-error"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when route id changes
  }, [wsNumberId, t]);

  const title = line?.name || line?.number || t("whatsapp");

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
          <Group gap="sm" mb="md" mt="md">
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={() => navigate("/whatsapp")}
              aria-label={t("whatsapp-back-to-lines")}
            >
              <IconArrowLeft size={20} />
            </ActionIcon>
            <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
              <Title order={2} lineClamp={1}>
                {title}
              </Title>
              {line ? (
                <Text size="sm" c="dimmed">
                  {line.number}
                  {line.agent?.name ? ` · ${line.agent.name}` : ""}
                </Text>
              ) : null}
            </Stack>
            {line ? (
              <Button
                size="sm"
                variant="light"
                leftSection={<IconMessages size={16} />}
                onClick={() =>
                  navigate(
                    `/dashboard?wsNumberId=${line.id}&channel=whatsapp`
                  )
                }
              >
                {t("view-conversations")}
              </Button>
            ) : null}
          </Group>

          {loading ? (
            <Stack align="center" py="xl">
              <Loader color="violet" />
            </Stack>
          ) : loadError || !line ? (
            <Stack gap="md">
              <Text c="red">{loadError || t("whatsapp-line-not-found")}</Text>
              <Button variant="default" onClick={() => navigate("/whatsapp")}>
                {t("whatsapp-back-to-lines")}
              </Button>
            </Stack>
          ) : (
            <Tabs value={activeTab} onChange={setActiveTab}>
              <Tabs.List mb="md">
                <Tabs.Tab
                  value="contacts"
                  leftSection={<IconUsers size={16} />}
                >
                  {t("whatsapp-tab-contacts")}
                </Tabs.Tab>
                <Tabs.Tab
                  value="settings"
                  leftSection={<IconSettings size={16} />}
                >
                  {t("whatsapp-tab-settings")}
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="contacts">
                <ContactsPanel line={line} />
              </Tabs.Panel>

              <Tabs.Panel value="settings">
                <SettingsPanel line={line} onRefresh={refreshLine} />
              </Tabs.Panel>
            </Tabs>
          )}
        </Box>
      </div>
    </main>
  );
}

function ContactsPanel({ line }: { line: WhatsappLine }) {
  const { t } = useTranslation();
  const [contacts, setContacts] = useState<TWhatsappContact[]>([]);
  const [contactsLoading, setContactsLoading] = useState(true);
  const [contactsError, setContactsError] = useState<string | null>(null);
  const [members, setMembers] = useState<TOrganizationMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [linkSelection, setLinkSelection] = useState<Record<number, string>>(
    {}
  );
  const [linkingId, setLinkingId] = useState<number | null>(null);

  useEffect(() => {
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
  }, [line.id, line.organization, t]);

  const memberOptions = useMemo(
    () => [
      { value: "", label: t("whatsapp-contact-select-member") },
      ...members.map((m) => ({
        value: String(m.id),
        label: m.profile_name || m.email || m.username || String(m.id),
      })),
    ],
    [members, t]
  );

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

  if (contactsLoading) {
    return (
      <Stack align="center" py="md">
        <Loader color="violet" size="sm" />
      </Stack>
    );
  }
  if (contactsError) {
    return <Text c="red">{contactsError}</Text>;
  }
  if (contacts.length === 0) {
    return <Text c="dimmed">{t("whatsapp-contacts-empty")}</Text>;
  }

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed" mb="xs">
        {t("whatsapp-contacts-title")}
      </Text>
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
                      data={memberOptions}
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
  );
}

function SettingsPanel({
  line,
  onRefresh,
}: {
  line: WhatsappLine;
  onRefresh: () => Promise<WhatsappLine | null>;
}) {
  const { t } = useTranslation();
  const hasOrg = line.organization != null && line.organization !== "";
  const [nameInput, setNameInput] = useState(line.name ?? "");
  const [capabilityState, setCapabilityState] = useState<Record<string, boolean>>(
    () => buildInitialCapabilityState(line.capabilities)
  );
  const [accessMode, setAccessMode] = useState<WhatsappAccessMode>(
    line.access_mode ?? "public"
  );
  const [allowedRoleIds, setAllowedRoleIds] = useState<string[]>(
    () => (line.allowed_roles || []).map((r) => r.id)
  );
  const [accessUserId, setAccessUserId] = useState<string>(
    line.access_user_id != null ? String(line.access_user_id) : ""
  );
  const [members, setMembers] = useState<TOrganizationMember[]>([]);
  const [roles, setRoles] = useState<TOrganizationRole[]>([]);
  const [accessSaving, setAccessSaving] = useState(false);

  useEffect(() => {
    setNameInput(line.name ?? "");
    setCapabilityState(buildInitialCapabilityState(line.capabilities));
    setAccessMode(line.access_mode ?? "public");
    setAllowedRoleIds((line.allowed_roles || []).map((r) => r.id));
    setAccessUserId(
      line.access_user_id != null ? String(line.access_user_id) : ""
    );
  }, [
    line.name,
    line.capabilities,
    line.number,
    line.id,
    line.access_mode,
    line.access_user_id,
    line.allowed_roles,
  ]);

  useEffect(() => {
    if (!hasOrg) {
      setMembers([]);
      setRoles([]);
      return;
    }
    let cancelled = false;
    const orgId = String(line.organization);
    Promise.all([
      getOrganizationMembers(orgId),
      getOrganizationRoles(orgId),
    ])
      .then(([memberRes, roleRes]) => {
        if (cancelled) return;
        setMembers(memberRes.filter((m) => m.is_active || m.is_owner));
        setRoles(roleRes.filter((r) => r.enabled));
      })
      .catch(() => {
        if (!cancelled) {
          setMembers([]);
          setRoles([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [hasOrg, line.organization]);

  const changeAgent = (slug: string) => {
    updateWhatsappNumber(line.number, { slug }).then(() => {
      toast.success(t("whatsapp-agent-changed"));
      void onRefresh();
    });
  };

  const updateName = () => {
    updateWhatsappNumber(line.number, { name: nameInput }).then(() => {
      toast.success(t("whatsapp-name-updated"));
      void onRefresh();
    });
  };

  const saveCapabilities = () => {
    const capabilities = buildCapabilitiesPayload(capabilityState);
    updateWhatsappNumber(line.number, { capabilities }).then(() => {
      toast.success(t("whatsapp-capabilities-saved"));
      void onRefresh();
    });
  };

  const saveAccess = async () => {
    const payload: {
      access_mode: WhatsappAccessMode;
      access_user_id?: number | null;
      allowed_role_ids?: string[];
    } = { access_mode: accessMode };

    if (accessMode === "roles") {
      payload.allowed_role_ids = allowedRoleIds;
    } else if (accessMode === "user") {
      payload.access_user_id = accessUserId ? Number(accessUserId) : null;
    } else {
      payload.access_user_id = null;
      payload.allowed_role_ids = [];
    }

    setAccessSaving(true);
    try {
      await updateWhatsappNumber(line.number, payload);
      toast.success(t("whatsapp-access-saved"));
      void onRefresh();
    } catch {
      toast.error(t("whatsapp-access-save-error"));
    } finally {
      setAccessSaving(false);
    }
  };

  const accessModeOptions = [
    { value: "public", label: t("whatsapp-access-public") },
    {
      value: "organization",
      label: t("whatsapp-access-organization"),
      disabled: !hasOrg,
    },
    {
      value: "roles",
      label: t("whatsapp-access-roles"),
      disabled: !hasOrg,
    },
    {
      value: "user",
      label: t("whatsapp-access-user"),
      disabled: !hasOrg,
    },
  ];

  const memberOptions = useMemo(
    () => [
      { value: "", label: t("whatsapp-access-select-user") },
      ...members.map((m) => ({
        value: String(m.id),
        label: m.profile_name || m.email || m.username || String(m.id),
      })),
    ],
    [members, t]
  );

  const roleOptions = useMemo(
    () => roles.map((r) => ({ value: r.id, label: r.name })),
    [roles]
  );

  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">
        {t("whatsapp-settings-title")}
      </Text>

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
          selectedSlug={line.agent.slug}
        />
      </div>

      <Stack gap="sm">
        <NativeSelect
          label={t("whatsapp-access-mode")}
          data={accessModeOptions}
          value={accessMode}
          onChange={(e) => {
            const val = e.currentTarget.value as WhatsappAccessMode;
            setAccessMode(val);
            if (val === "public" || val === "organization") {
              setAllowedRoleIds([]);
              setAccessUserId("");
            }
          }}
        />
        {!hasOrg && accessMode !== "public" && (
          <Text size="xs" c="dimmed">
            {t("whatsapp-access-no-org")}
          </Text>
        )}
        {accessMode === "roles" && hasOrg && (
          <>
            <MultiSelect
              label={t("whatsapp-access-roles-label")}
              data={roleOptions}
              value={allowedRoleIds}
              onChange={setAllowedRoleIds}
              searchable
              nothingFoundMessage={t("whatsapp-access-no-roles")}
            />
            <Text size="xs" c="dimmed">
              {t("whatsapp-access-roles-owner-note")}
            </Text>
          </>
        )}
        {accessMode === "user" && hasOrg && (
          <NativeSelect
            label={t("whatsapp-access-user-label")}
            data={memberOptions}
            value={accessUserId}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setAccessUserId(val);
            }}
          />
        )}
        <Button
          leftSection={<IconDeviceFloppy size={16} />}
          variant="default"
          loading={accessSaving}
          onClick={() => void saveAccess()}
          disabled={!hasOrg && accessMode !== "public"}
        >
          {t("whatsapp-save-access")}
        </Button>
      </Stack>

      <div>
        <CapabilitiesChecklist
          label={t("whatsapp-capabilities")}
          names={WHATSAPP_CAPABILITY_NAMES}
          requiredNames={WHATSAPP_REQUIRED_CAPABILITY_NAMES}
          value={capabilityState}
          onChange={setCapabilityState}
        />
        <Text size="xs" c="dimmed" mt="xs">
          {t("whatsapp-capabilities-risk-note")}
        </Text>
        <Button
          mt="sm"
          leftSection={<IconDeviceFloppy size={16} />}
          variant="default"
          onClick={saveCapabilities}
        >
          {t("whatsapp-save-capabilities")}
        </Button>
      </div>
    </Stack>
  );
}
