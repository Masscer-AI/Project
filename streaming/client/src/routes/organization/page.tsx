import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  assignRoleToMember,
  createOrganization,
  createOrganizationRole,
  deleteOrganizationRole,
  getFeatureFlagNames,
  getOrganizationMembers,
  getOrganizationRoles,
  getUserOrganizations,
  removeRoleAssignment,
  TOrganizationData,
  updateOrganization,
  updateOrganizationRole,
} from "../../modules/apiCalls";
import { titlelify } from "../../modules/utils";
import { API_URL } from "../../modules/constants";
import {
  TOrganization,
  TOrganizationMember,
  TOrganizationRole,
} from "../../types";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { QRCodeDisplay } from "../../components/QRGenerator/QRGenerator";
import { useForm } from "@mantine/form";

import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Checkbox,
  Divider,
  FileButton,
  Group,
  Image,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import {
  IconBuilding,
  IconCopy,
  IconDeviceFloppy,
  IconLink,
  IconMenu2,
  IconPlus,
  IconShield,
  IconUsers,
} from "@tabler/icons-react";

export default function OrganizationPage() {
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));
  const { t } = useTranslation();
  const [orgs, setOrgs] = useState<TOrganization[]>([]);
  const [members, setMembers] = useState<TOrganizationMember[]>([]);
  const [roles, setRoles] = useState<TOrganizationRole[]>([]);
  const [featureFlagNames, setFeatureFlagNames] = useState<
    { name: string; organization_only: boolean }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [assigningUserId, setAssigningUserId] = useState<number | null>(null);

  // Role form
  const [roleModalOpened, setRoleModalOpened] = useState(false);
  const [editingRole, setEditingRole] = useState<TOrganizationRole | null>(
    null
  );
  const [roleForm, setRoleForm] = useState({
    name: "",
    description: "",
    capabilities: [] as string[],
  });

  // Organization settings
  const orgForm = useForm({
    initialValues: {
      name: "",
      description: "",
    },
  });
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [deleteLogo, setDeleteLogo] = useState(false);
  const [savingOrg, setSavingOrg] = useState(false);
  const [logoCacheKey, setLogoCacheKey] = useState(0);

  // Create organization
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", description: "" });
  const [creating, setCreating] = useState(false);

  // Invite link
  const [showInviteLink, setShowInviteLink] = useState(false);

  const loadOrgs = async () => {
    try {
      const data = await getUserOrganizations();
      setOrgs(data.filter((o: TOrganization) => o.is_owner || o.can_manage));
    } catch {
      setOrgs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrgs();
  }, []);

  const org = orgs[0] ?? null;

  useEffect(() => {
    if (org) {
      orgForm.setValues({
        name: org.name,
        description: org.description || "",
      });
      orgForm.resetDirty();
      setLogoFile(null);
      setDeleteLogo(false);
      setLogoCacheKey(Date.now());
    }
  }, [org?.id]);

  useEffect(() => {
    if (!org?.id) {
      setMembers([]);
      return;
    }
    setLoadingMembers(true);
    getOrganizationMembers(org.id)
      .then(setMembers)
      .catch(() => setMembers([]))
      .finally(() => setLoadingMembers(false));
  }, [org?.id]);

  useEffect(() => {
    if (!org?.id) {
      setRoles([]);
      return;
    }
    setLoadingRoles(true);
    getOrganizationRoles(org.id)
      .then(setRoles)
      .catch(() => setRoles([]))
      .finally(() => setLoadingRoles(false));
  }, [org?.id]);

  useEffect(() => {
    getFeatureFlagNames()
      .then(setFeatureFlagNames)
      .catch(() => setFeatureFlagNames([]));
  }, []);

  const inviteUrl = org
    ? `${window.location.origin}/signup?orgId=${org.id}`
    : "";

  const reloadMembers = () => {
    if (org?.id)
      getOrganizationMembers(org.id)
        .then(setMembers)
        .catch(() => setMembers([]));
  };

  const reloadRoles = () => {
    if (org?.id)
      getOrganizationRoles(org.id)
        .then(setRoles)
        .catch(() => setRoles([]));
  };

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleCreateOrg = async () => {
    if (!createForm.name.trim()) {
      toast.error(t("organization-name-required"));
      return;
    }
    setCreating(true);
    const tid = toast.loading(t("loading"));
    try {
      await createOrganization(createForm as TOrganizationData);
      toast.success(t("organization-created"));
      setShowCreateForm(false);
      setCreateForm({ name: "", description: "" });
      await loadOrgs();
    } catch (e: any) {
      toast.error(
        e?.response?.data?.detail || t("an-error-occurred")
      );
    } finally {
      toast.dismiss(tid);
      setCreating(false);
    }
  };

  const handleSaveOrgSettings = async () => {
    if (!org?.id || !orgForm.values.name.trim()) return;
    setSavingOrg(true);
    const tid = toast.loading(t("loading"));
    try {
      let options: { logoFile?: File; deleteLogo: boolean } | undefined;
      if (logoFile) {
        options = { logoFile, deleteLogo: false };
      } else if (deleteLogo) {
        options = { deleteLogo: true };
      }
      await updateOrganization(org.id, orgForm.values, options);
      toast.success(t("organization-updated"));
      setLogoFile(null);
      setDeleteLogo(false);
      orgForm.resetDirty();
      setLogoCacheKey(Date.now());
      await loadOrgs();
    } catch (e: any) {
      toast.error(
        e?.response?.data?.detail || t("error-updating-organization")
      );
    } finally {
      toast.dismiss(tid);
      setSavingOrg(false);
    }
  };

  const isOrgDirty = orgForm.isDirty() || !!logoFile || deleteLogo;
  const logoSrc = org?.logo_url ? `${API_URL}${org.logo_url}?v=${logoCacheKey}` : null;
  const handleSaveRole = async () => {
    if (!org?.id || !roleForm.name.trim()) return;
    const tid = toast.loading(t("loading"));
    try {
      if (editingRole) {
        await updateOrganizationRole(org.id, editingRole.id, {
          name: roleForm.name.trim(),
          description: roleForm.description.trim() || undefined,
          capabilities: roleForm.capabilities,
        });
        toast.success(t("role-updated"));
      } else {
        await createOrganizationRole(org.id, {
          name: roleForm.name.trim(),
          description: roleForm.description.trim() || undefined,
          capabilities: roleForm.capabilities,
        });
        toast.success(t("role-created"));
      }
      setRoleModalOpened(false);
      setEditingRole(null);
      setRoleForm({ name: "", description: "", capabilities: [] });
      reloadRoles();
    } catch (e: any) {
      toast.error(
        e?.response?.data?.name?.[0] ||
          e?.response?.data?.detail ||
          t("an-error-occurred")
      );
    } finally {
      toast.dismiss(tid);
    }
  };

  const handleDeleteRole = async (role: TOrganizationRole) => {
    const tid = toast.loading(t("loading"));
    try {
      await deleteOrganizationRole(org!.id, role.id);
      toast.success(t("role-deleted"));
      reloadRoles();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
    }
  };

  const handleAssignRole = async (userId: number, roleId: string | null) => {
    if (!org?.id) return;
    setAssigningUserId(userId);
    const tid = toast.loading(t("loading"));
    try {
      if (roleId) {
        await assignRoleToMember(org.id, {
          user_id: userId,
          role_id: roleId,
        });
        toast.success(t("role-assigned"));
      } else {
        const member = members.find((m) => m.id === userId);
        const aid = member?.current_role?.assignment_id;
        if (aid) {
          await removeRoleAssignment(org.id, aid);
          toast.success(t("role-removed"));
        }
      }
      reloadMembers();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
      setAssigningUserId(null);
    }
  };

  const openCreateRole = () => {
    setEditingRole(null);
    setRoleForm({ name: "", description: "", capabilities: [] });
    setRoleModalOpened(true);
  };

  const openEditRole = (role: TOrganizationRole) => {
    setEditingRole(role);
    setRoleForm({
      name: role.name,
      description: role.description || "",
      capabilities: role.capabilities || [],
    });
    setRoleModalOpened(true);
  };

  const copyInviteLink = () => {
    if (!inviteUrl) return;
    navigator.clipboard.writeText(inviteUrl);
    toast.success(t("copied-to-clipboard"));
  };

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <main className="d-flex pos-relative h-viewport">
        <Sidebar />
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
        >
          <Stack align="center" justify="center" pt="xl">
            <Loader color="violet" />
          </Stack>
        </div>
      </main>
    );
  }

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
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={toggleSidebar}
            >
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box px="md" w="100%" maw="42rem" mx="auto">
          <Title order={2} ta="center" mb="lg" mt="md">
            {org ? t("manage-organization") : t("organization")}
          </Title>

          {!org ? (
            /* ── No organization ── */
            <Card withBorder p="xl">
              {!showCreateForm ? (
                <Stack align="center" gap="md" py="xl">
                  <Text c="dimmed">{t("no-organizations-message")}</Text>
                  <Button
                    leftSection={<IconPlus size={16} />}
                    onClick={() => setShowCreateForm(true)}
                  >
                    {t("create-organization")}
                  </Button>
                </Stack>
              ) : (
                <Stack gap="md">
                  <Title order={4}>{t("create-organization")}</Title>
                  <TextInput
                    label={t("organization-name")}
                    placeholder={t("name-for-your-organization")}
                    value={createForm.name}
                    onChange={(e) =>
                      setCreateForm({
                        ...createForm,
                        name: e.currentTarget.value,
                      })
                    }
                  />
                  <Textarea
                    label={t("describe-your-organization")}
                    placeholder={t("describe-your-organization")}
                    value={createForm.description}
                    onChange={(e) =>
                      setCreateForm({
                        ...createForm,
                        description: e.currentTarget.value,
                      })
                    }
                    autosize
                    minRows={3}
                  />
                  <Group>
                    <Button
                      onClick={handleCreateOrg}
                      loading={creating}
                      flex={1}
                    >
                      {t("create")}
                    </Button>
                    <Button
                      variant="default"
                      onClick={() => {
                        setShowCreateForm(false);
                        setCreateForm({ name: "", description: "" });
                      }}
                    >
                      {t("cancel")}
                    </Button>
                  </Group>
                </Stack>
              )}
            </Card>
          ) : (
            /* ── Organization exists — Tabs ── */
            <Tabs defaultValue="settings" variant="outline">
              <Tabs.List mb="md">
                <Tabs.Tab
                  value="settings"
                  leftSection={<IconBuilding size={16} />}
                >
                  {t("settings")}
                </Tabs.Tab>
                <Tabs.Tab
                  value="roles"
                  leftSection={<IconShield size={16} />}
                >
                  {t("roles")}
                </Tabs.Tab>
                <Tabs.Tab
                  value="members"
                  leftSection={<IconUsers size={16} />}
                >
                  {t("members")}
                </Tabs.Tab>
              </Tabs.List>

              {/* ── Settings Tab ── */}
              <Tabs.Panel value="settings">
                <Card withBorder p="lg">
                  <Group justify="space-between" mb="md">
                    <Title order={4}>{t("organization-settings")}</Title>
                  </Group>

                  <Stack gap="md">
                    {/* Logo */}
                    <Stack gap={4}>
                      <Text size="sm" c="dimmed">
                        {t("organization-logo")}
                      </Text>
                      <Group gap="md" align="center">
                        {logoSrc && !deleteLogo && !logoFile ? (
                          <Image
                            src={logoSrc}
                            alt={org.name}
                            radius="sm"
                            w={64}
                            h={64}
                            fit="cover"
                          />
                        ) : logoFile ? (
                          <LogoPreview file={logoFile} />
                        ) : (
                          <Box
                            w={64}
                            h={64}
                            bg="rgba(255,255,255,0.05)"
                            style={{
                              borderRadius: 8,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                            }}
                          >
                            <Text size="xs" c="dimmed">
                              {t("no-logo")}
                            </Text>
                          </Box>
                        )}
                        <Group gap="xs">
                          <FileButton
                            onChange={(f) => {
                              if (f) {
                                setLogoFile(f);
                                setDeleteLogo(false);
                              }
                            }}
                            accept="image/*"
                          >
                            {(props) => (
                              <Button variant="default" size="xs" {...props}>
                                {t("change-logo")}
                              </Button>
                            )}
                          </FileButton>
                          {(org.logo_url || logoFile) && !deleteLogo && (
                            <Button
                              variant="default"
                              size="xs"
                              color="red"
                              onClick={() => {
                                setDeleteLogo(true);
                                setLogoFile(null);
                              }}
                            >
                              {t("remove-logo")}
                            </Button>
                          )}
                        </Group>
                      </Group>
                    </Stack>

                    <TextInput
                      label={t("organization-name")}
                      required
                      {...orgForm.getInputProps("name")}
                    />
                    <Textarea
                      label={t("describe-your-organization")}
                      autosize
                      minRows={3}
                      {...orgForm.getInputProps("description")}
                    />
                    <Group gap="sm">
                      <Button
                        leftSection={<IconDeviceFloppy size={16} />}
                        onClick={handleSaveOrgSettings}
                        loading={savingOrg}
                        disabled={!isOrgDirty}
                        flex={1}
                      >
                        {t("save")}
                      </Button>
                      <Button
                        variant="default"
                        disabled={!isOrgDirty}
                        onClick={() => {
                          orgForm.setValues({
                            name: org.name,
                            description: org.description || "",
                          });
                          orgForm.resetDirty();
                          setLogoFile(null);
                          setDeleteLogo(false);
                        }}
                      >
                        {t("cancel")}
                      </Button>
                    </Group>
                  </Stack>
                </Card>
              </Tabs.Panel>

              {/* ── Roles Tab ── */}
              <Tabs.Panel value="roles">
                <Card withBorder p="lg">
                  <Group justify="space-between" mb="md">
                    <Title order={4}>{t("roles")}</Title>
                    <Button
                      variant="default"
                      size="xs"
                      leftSection={<IconPlus size={14} />}
                      onClick={openCreateRole}
                    >
                      {t("create-role")}
                    </Button>
                  </Group>

                  {loadingRoles ? (
                    <Stack align="center" py="xl">
                      <Loader color="violet" size="sm" />
                    </Stack>
                  ) : roles.length === 0 ? (
                    <Text c="dimmed" ta="center" py="xl">
                      {t("no-roles-yet")}
                    </Text>
                  ) : (
                    <Stack gap="sm">
                      {roles.map((role) => (
                        <Card
                          key={role.id}
                          withBorder
                          p="sm"
                          style={{ background: "rgba(255,255,255,0.02)" }}
                        >
                          <Group justify="space-between" wrap="nowrap">
                            <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
                              <Text fw={500}>{role.name}</Text>
                              {role.description && (
                                <Text size="sm" c="dimmed">
                                  {role.description}
                                </Text>
                              )}
                              {role.capabilities?.length > 0 && (
                                <Group gap={4} mt={4}>
                                  {role.capabilities.map((c) => (
                                    <Badge
                                      key={c}
                                      size="xs"
                                      variant="default"
                                    >
                                      {titlelify(c)}
                                    </Badge>
                                  ))}
                                </Group>
                              )}
                            </Stack>
                            <Group gap="xs" wrap="nowrap">
                              <Button
                                variant="default"
                                size="xs"
                                onClick={() => openEditRole(role)}
                              >
                                {t("edit")}
                              </Button>
                              <Button
                                variant="light"
                                color="red"
                                size="xs"
                                onClick={() => handleDeleteRole(role)}
                              >
                                {t("delete")}
                              </Button>
                            </Group>
                          </Group>
                        </Card>
                      ))}
                    </Stack>
                  )}
                </Card>
              </Tabs.Panel>

              {/* ── Members Tab ── */}
              <Tabs.Panel value="members">
                <Stack gap="md">
                  {/* Invite link section */}
                  <Card withBorder p="lg">
                    <Group justify="space-between" mb={showInviteLink ? "md" : 0}>
                      <Title order={4}>{t("invite-link")}</Title>
                      <Button
                        variant="default"
                        size="xs"
                        leftSection={<IconLink size={14} />}
                        onClick={() => setShowInviteLink(!showInviteLink)}
                      >
                        {showInviteLink
                          ? t("hide")
                          : t("generate-invite-link")}
                      </Button>
                    </Group>

                    {showInviteLink && (
                      <Stack gap="md">
                        <Text size="sm" c="dimmed">
                          {t("invite-link-description")}
                        </Text>
                        <Group gap="sm" align="end">
                          <TextInput
                            readOnly
                            value={inviteUrl}
                            style={{ flex: 1 }}
                            styles={{
                              input: { cursor: "text" },
                            }}
                          />
                          <Button
                            variant="default"
                            leftSection={<IconCopy size={16} />}
                            onClick={copyInviteLink}
                          >
                            {t("copy")}
                          </Button>
                        </Group>
                        <Divider />
                        <Group justify="center">
                          <QRCodeDisplay url={inviteUrl} size={180} />
                        </Group>
                      </Stack>
                    )}
                  </Card>

                  {/* Members list */}
                  <Card withBorder p="lg">
                    <Title order={4} mb="md">
                      {t("members")}
                    </Title>

                    {loadingMembers ? (
                      <Stack align="center" py="xl">
                        <Loader color="violet" size="sm" />
                      </Stack>
                    ) : members.length === 0 ? (
                      <Text c="dimmed" ta="center" py="xl">
                        {t("no-members-yet")}
                      </Text>
                    ) : (
                      <Stack gap="sm">
                        {members.map((m) => (
                          <Card
                            key={m.id}
                            withBorder
                            p="sm"
                            style={{
                              background: "rgba(255,255,255,0.02)",
                            }}
                          >
                            <Group
                              justify="space-between"
                              wrap="nowrap"
                              gap="sm"
                            >
                              <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
                                <Text fw={500} truncate>
                                  {m.profile_name ||
                                    m.username ||
                                    m.email ||
                                    String(m.id)}
                                </Text>
                                <Text size="sm" c="dimmed" truncate>
                                  {m.email}
                                </Text>
                              </Stack>
                              <Group gap="xs" wrap="nowrap" align="center">
                                {m.is_owner && (
                                  <Badge color="violet" size="sm">
                                    {t("owner")}
                                  </Badge>
                                )}
                                {!m.is_owner && (
                                  <NativeSelect
                                    size="xs"
                                    value={m.current_role?.id ?? ""}
                                    onChange={(e) => {
                                      const v = e.currentTarget.value;
                                      handleAssignRole(m.id, v || null);
                                    }}
                                    disabled={assigningUserId === m.id}
                                    data={[
                                      {
                                        value: "",
                                        label: `— ${t("no-role")} —`,
                                      },
                                      ...roles.map((r) => ({
                                        value: r.id,
                                        label: r.name,
                                      })),
                                    ]}
                                    style={{ minWidth: 130 }}
                                  />
                                )}
                              </Group>
                            </Group>
                          </Card>
                        ))}
                      </Stack>
                    )}
                  </Card>
                </Stack>
              </Tabs.Panel>
            </Tabs>
          )}
        </Box>
      </div>

      {/* ── Role create/edit modal ── */}
      <Modal
        opened={roleModalOpened}
        onClose={() => {
          setRoleModalOpened(false);
          setEditingRole(null);
          setRoleForm({ name: "", description: "", capabilities: [] });
        }}
        title={editingRole ? t("edit-role") : t("create-role")}
        centered
      >
        <Stack gap="md">
          <TextInput
            label={t("role-name-placeholder")}
            value={roleForm.name}
            onChange={(e) =>
              setRoleForm({ ...roleForm, name: e.currentTarget.value })
            }
          />
          <Textarea
            label={t("role-description-placeholder")}
            value={roleForm.description}
            onChange={(e) =>
              setRoleForm({
                ...roleForm,
                description: e.currentTarget.value,
              })
            }
            autosize
            minRows={2}
          />
          <Stack gap="xs">
            <Text size="sm" c="dimmed">
              {t("capabilities")}
            </Text>
            {featureFlagNames.filter((f) => !f.organization_only).length ===
            0 ? (
              <Text size="sm" c="dimmed">
                {t("no-capabilities-available")}
              </Text>
            ) : (
              <Stack gap="xs">
                {featureFlagNames
                  .filter((f) => !f.organization_only)
                  .map((flag) => (
                    <Checkbox
                      key={flag.name}
                      label={titlelify(flag.name)}
                      checked={roleForm.capabilities.includes(flag.name)}
                      onChange={(e) => {
                        const checked = e.currentTarget.checked;
                        setRoleForm((f) => ({
                          ...f,
                          capabilities: checked
                            ? [...f.capabilities, flag.name]
                            : f.capabilities.filter((c) => c !== flag.name),
                        }));
                      }}
                    />
                  ))}
              </Stack>
            )}
          </Stack>
          <Group>
            <Button onClick={handleSaveRole} flex={1}>
              {editingRole ? t("update") : t("create")}
            </Button>
            <Button
              variant="default"
              onClick={() => {
                setRoleModalOpened(false);
                setEditingRole(null);
                setRoleForm({ name: "", description: "", capabilities: [] });
              }}
            >
              {t("cancel")}
            </Button>
          </Group>
        </Stack>
      </Modal>

    </main>
  );
}

// ── Helper: Logo preview ──────────────────────────────────────────────────────

const LogoPreview = ({ file }: { file: File }) => {
  const [src, setSrc] = useState<string>("");
  useEffect(() => {
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return <Image src={src} alt="Preview" radius="sm" w={64} h={64} fit="cover" />;
};
