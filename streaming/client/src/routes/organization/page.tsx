import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  assignRoleToMember,
  buyCredits,
  createCheckoutSession,
  createOrganization,
  createOrganizationMember,
  createOrganizationRole,
  deactivateOrganizationMember,
  deleteOrganizationRole,
  getFeatureFlagNames,
  getOrganizationBilling,
  getOrganizationMembers,
  getOrganizationRoles,
  getUserOrganizations,
  removeOrganizationMember,
  removeRoleAssignment,
  TOrganizationData,
  updateOrganization,
  updateOrganizationMemberProfile,
  updateOrganizationRole,
} from "../../modules/apiCalls";
import { API_URL } from "../../modules/constants";
import {
  TOrganization,
  TOrganizationBilling,
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
  Tooltip,
} from "@mantine/core";
import {
  IconBuilding,
  IconCopy,
  IconCreditCard,
  IconDeviceFloppy,
  IconEdit,
  IconLink,
  IconMenu2,
  IconPlayerPause,
  IconPlayerPlay,
  IconPlus,
  IconQuestionMark,
  IconShield,
  IconTrash,
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
  const [billing, setBilling] = useState<TOrganizationBilling | null>(null);
  const [loadingBilling, setLoadingBilling] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [creditAmount, setCreditAmount] = useState<number>(25);
  const [buyingCredits, setBuyingCredits] = useState(false);

  const handleBuyCredits = async () => {
    if (!org?.id) return;
    setBuyingCredits(true);
    try {
      const { checkout_url } = await buyCredits(org.id, creditAmount);
      window.location.href = checkout_url;
    } catch (e) {
      toast.error("Could not start checkout. Please try again.");
    } finally {
      setBuyingCredits(false);
    }
  };

  const handleSubscribe = async (planSlug: "organization" | "pay_as_you_go") => {
    if (!org?.id) return;
    setCheckoutLoading(planSlug);
    try {
      const { checkout_url } = await createCheckoutSession(org.id, planSlug);
      window.location.href = checkout_url;
    } catch (e) {
      toast.error("Could not start checkout. Please try again.");
    } finally {
      setCheckoutLoading(null);
    }
  };
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

  // Member action confirmation modal
  const [memberAction, setMemberAction] = useState<{
    member: TOrganizationMember;
    action: "deactivate" | "reactivate" | "remove";
  } | null>(null);
  const [memberActionLoading, setMemberActionLoading] = useState(false);

  // Create member modal
  const [createMemberOpened, setCreateMemberOpened] = useState(false);
  const [createMemberForm, setCreateMemberForm] = useState({
    username: "",
    email: "",
    password: "",
    name: "",
    bio: "",
    expires_at: "",
  });
  const [createMemberLoading, setCreateMemberLoading] = useState(false);

  // Edit member modal
  const [editingMember, setEditingMember] = useState<TOrganizationMember | null>(null);
  const [editMemberForm, setEditMemberForm] = useState({
    name: "",
    bio: "",
    expires_at: "",
  });
  const [editMemberLoading, setEditMemberLoading] = useState(false);

  // Members tab filter
  const [memberTab, setMemberTab] = useState<"active" | "inactive" | "expired">("active");

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
    if (!org?.id) { setBilling(null); return; }
    setLoadingBilling(true);
    getOrganizationBilling(org.id)
      .then(setBilling)
      .catch(() => setBilling(null))
      .finally(() => setLoadingBilling(false));
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
        await removeRoleAssignment(org.id, {
          userId,
          assignmentId: member?.current_role?.assignment_id,
        });
        toast.success(t("role-removed"));
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

  const openMemberAction = (
    member: TOrganizationMember,
    action: "deactivate" | "reactivate" | "remove"
  ) => {
    setMemberAction({ member, action });
  };

  const closeMemberAction = () => {
    setMemberAction(null);
    setMemberActionLoading(false);
  };

  const confirmMemberAction = async () => {
    if (!org?.id || !memberAction) return;
    setMemberActionLoading(true);
    const tid = toast.loading(t("loading"));
    try {
      const { member, action } = memberAction;
      if (action === "remove") {
        await removeOrganizationMember(org.id, member.id);
        toast.success(t("member-removed"));
      } else {
        const newStatus = action === "reactivate";
        await deactivateOrganizationMember(org.id, member.id, newStatus);
        toast.success(
          newStatus ? t("member-reactivated") : t("member-deactivated")
        );
      }
      reloadMembers();
      closeMemberAction();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
      setMemberActionLoading(false);
    }
  };

  const isExpired = (m: TOrganizationMember) => {
    if (!m.expires_at) return false;
    return new Date(m.expires_at) < new Date();
  };

  const handleCreateMember = async () => {
    if (!org?.id) return;
    const { username, email, password, name, bio, expires_at } = createMemberForm;
    if (!username.trim() || !email.trim() || !password) {
      toast.error(t("username-required-hint"));
      return;
    }
    setCreateMemberLoading(true);
    const tid = toast.loading(t("loading"));
    try {
      const newMember = await createOrganizationMember(org.id, {
        username: username.trim(),
        email: email.trim(),
        password,
        name: name.trim() || undefined,
        bio: bio.trim() || undefined,
        expires_at: expires_at ? new Date(expires_at).toISOString() : null,
      });
      setMembers((prev) => [...prev, newMember]);
      setCreateMemberOpened(false);
      setCreateMemberForm({ username: "", email: "", password: "", name: "", bio: "", expires_at: "" });
      toast.success(t("member-created"));
    } catch (e: any) {
      toast.error(e?.response?.data?.error || t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
      setCreateMemberLoading(false);
    }
  };

  const openEditMember = (m: TOrganizationMember) => {
    setEditingMember(m);
    const localExpires = m.expires_at
      ? (() => {
          const d = new Date(m.expires_at);
          const pad = (n: number) => String(n).padStart(2, "0");
          return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        })()
      : "";
    setEditMemberForm({ name: m.profile_name, bio: m.bio, expires_at: localExpires });
  };

  const handleEditMember = async () => {
    if (!org?.id || !editingMember) return;
    setEditMemberLoading(true);
    const tid = toast.loading(t("loading"));
    try {
      const expiresPayload = editMemberForm.expires_at
        ? new Date(editMemberForm.expires_at).toISOString()
        : null;
      await updateOrganizationMemberProfile(org.id, editingMember.id, {
        name: editMemberForm.name,
        bio: editMemberForm.bio,
        expires_at: expiresPayload,
      });
      toast.success(t("member-updated"));
      setEditingMember(null);
      reloadMembers();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
      setEditMemberLoading(false);
    }
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
                <Tabs.Tab
                  value="billing"
                  leftSection={<IconCreditCard size={16} />}
                >
                  {t("billing")}
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
                                    <Tooltip
                                      key={c}
                                      label={t(`ff-${c}-desc`)}
                                      multiline
                                      w={250}
                                      withArrow
                                    >
                                      <Badge
                                        size="xs"
                                        variant="default"
                                        style={{ cursor: "help" }}
                                      >
                                        {t(`ff-${c}`)}
                                      </Badge>
                                    </Tooltip>
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
                    <Group justify="space-between" mb="md">
                      <Title order={4}>{t("members")}</Title>
                      <Button
                        size="xs"
                        leftSection={<IconPlus size={14} />}
                        onClick={() => setCreateMemberOpened(true)}
                      >
                        {t("create-member")}
                      </Button>
                    </Group>

                    <Tabs value={memberTab} onChange={(v) => setMemberTab(v as typeof memberTab)} mb="sm">
                      <Tabs.List>
                        <Tabs.Tab value="active">{t("members-tab-active")}</Tabs.Tab>
                        <Tabs.Tab value="inactive">{t("members-tab-inactive")}</Tabs.Tab>
                        <Tabs.Tab value="expired">{t("members-tab-expired")}</Tabs.Tab>
                      </Tabs.List>
                    </Tabs>

                    {loadingMembers ? (
                      <Stack align="center" py="xl">
                        <Loader color="violet" size="sm" />
                      </Stack>
                    ) : members.filter((m) => {
                        if (memberTab === "expired") return isExpired(m);
                        if (memberTab === "inactive") return !isExpired(m) && m.is_active === false;
                        return !isExpired(m) && m.is_active !== false;
                      }).length === 0 ? (
                      <Text c="dimmed" ta="center" py="xl">
                        {t("no-members-yet")}
                      </Text>
                    ) : (
                      <Stack gap="sm">
                        {members
                          .filter((m) => {
                            if (memberTab === "expired") return isExpired(m);
                            if (memberTab === "inactive") return !isExpired(m) && m.is_active === false;
                            return !isExpired(m) && m.is_active !== false;
                          })
                          .map((m) => (
                          <Card
                            key={m.id}
                            withBorder
                            p="sm"
                            style={{
                              background: "rgba(255,255,255,0.02)",
                              opacity: m.is_active === false || isExpired(m) ? 0.55 : 1,
                            }}
                          >
                            <Group
                              justify="space-between"
                              wrap="nowrap"
                              gap="sm"
                            >
                              <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
                                <Group gap="xs">
                                  <Text fw={500} truncate>
                                    {m.profile_name ||
                                      m.username ||
                                      m.email ||
                                      String(m.id)}
                                  </Text>
                                  {m.is_active === false && (
                                    <Badge color="gray" size="xs" variant="outline">
                                      {t("deactivated")}
                                    </Badge>
                                  )}
                                  {isExpired(m) && (
                                    <Badge color="red" size="xs" variant="outline">
                                      {t("expired")}
                                    </Badge>
                                  )}
                                  {!isExpired(m) && m.expires_at && (() => {
                                    const hoursLeft = (new Date(m.expires_at).getTime() - Date.now()) / 3600000;
                                    return hoursLeft < 24 ? (
                                      <Badge color="yellow" size="xs" variant="outline">
                                        {t("expires-soon")}
                                      </Badge>
                                    ) : null;
                                  })()}
                                </Group>
                                <Text size="sm" c="dimmed" truncate>
                                  {m.email}
                                </Text>
                                {m.expires_at && (
                                  <Text size="xs" c="dimmed">
                                    {isExpired(m) ? t("expired") : t("expires")}: {new Date(m.expires_at).toLocaleString()}
                                  </Text>
                                )}
                              </Stack>
                              <Group gap="xs" wrap="nowrap" align="center">
                                {m.is_owner && (
                                  <Badge color="violet" size="sm">
                                    {t("owner")}
                                  </Badge>
                                )}
                                {!m.is_owner && (
                                  <>
                                    <NativeSelect
                                      size="xs"
                                      value={m.current_role?.id ?? ""}
                                      onChange={(e) => {
                                        const v = e.currentTarget.value;
                                        handleAssignRole(m.id, v || null);
                                      }}
                                      disabled={
                                        assigningUserId === m.id ||
                                        m.is_active === false
                                      }
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
                                    <ActionIcon
                                      variant="subtle"
                                      color="blue"
                                      size="sm"
                                      title={t("edit-member")}
                                      onClick={() => openEditMember(m)}
                                    >
                                      <IconEdit size={16} />
                                    </ActionIcon>
                                    <ActionIcon
                                      variant="subtle"
                                      color={
                                        m.is_active === false
                                          ? "green"
                                          : "yellow"
                                      }
                                      size="sm"
                                      title={
                                        m.is_active === false
                                          ? t("reactivate")
                                          : t("deactivate")
                                      }
                                      onClick={() =>
                                        openMemberAction(
                                          m,
                                          m.is_active === false
                                            ? "reactivate"
                                            : "deactivate"
                                        )
                                      }
                                    >
                                      {m.is_active === false ? (
                                        <IconPlayerPlay size={16} />
                                      ) : (
                                        <IconPlayerPause size={16} />
                                      )}
                                    </ActionIcon>
                                    <ActionIcon
                                      variant="subtle"
                                      color="red"
                                      size="sm"
                                      title={t("remove-member")}
                                      onClick={() =>
                                        openMemberAction(m, "remove")
                                      }
                                    >
                                      <IconTrash size={16} />
                                    </ActionIcon>
                                  </>
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

              {/* ── Billing Tab ── */}
              <Tabs.Panel value="billing">
                <Stack gap="md">
                  {loadingBilling ? (
                    <Loader size="sm" />
                  ) : !billing ? (
                    <Text c="dimmed" size="sm">{t("no-billing-info")}</Text>
                  ) : (
                    <>
                      {/* Subscription card */}
                      <Card withBorder p="lg">
                        <Group justify="space-between" mb="md">
                          <Title order={4}>{t("subscription")}</Title>
                          {billing.subscription && (
                            <Badge
                              color={
                                billing.subscription.status === "active" ? "green"
                                : billing.subscription.status === "trial" ? "blue"
                                : billing.subscription.status === "expired" ? "red"
                                : billing.subscription.status === "pending_payment" ? "orange"
                                : "gray"
                              }
                              variant="light"
                              size="lg"
                            >
                              {billing.subscription.status.replace("_", " ")}
                            </Badge>
                          )}
                        </Group>

                        {!billing.subscription ? (
                          <Text c="dimmed" size="sm">{t("no-subscription")}</Text>
                        ) : (
                          <Stack gap="xs">
                            <Group gap="xs">
                              <Text size="sm" fw={600} w={160}>{t("plan")}</Text>
                              <Text size="sm">{billing.subscription.plan.display_name}</Text>
                            </Group>
                            <Group gap="xs">
                              <Text size="sm" fw={600} w={160}>{t("payment-method")}</Text>
                              <Badge variant="outline" size="sm">
                                {billing.subscription.payment_method}
                              </Badge>
                            </Group>
                            <Group gap="xs">
                              <Text size="sm" fw={600} w={160}>{t("monthly-price")}</Text>
                              <Text size="sm">
                                {parseFloat(billing.subscription.plan.monthly_price_usd) === 0
                                  ? t("free")
                                  : `$${billing.subscription.plan.monthly_price_usd} USD / mo`}
                              </Text>
                            </Group>
                            {billing.subscription.end_date && (
                              <Group gap="xs">
                                <Text size="sm" fw={600} w={160}>{t("expires")}</Text>
                                <Text size="sm">
                                  {new Date(billing.subscription.end_date).toLocaleDateString()}
                                </Text>
                              </Group>
                            )}
                          </Stack>
                        )}
                      </Card>

                      {/* Wallet / credits card */}
                      <Card withBorder p="lg">
                        <Title order={4} mb="md">{t("credits")}</Title>

                        {!billing.wallet ? (
                          <Text c="dimmed" size="sm">{t("no-wallet")}</Text>
                        ) : (
                          <Stack gap="sm">
                            <Group justify="space-between" align="flex-end">
                              <Stack gap={2}>
                                <Text size="xs" c="dimmed">{t("available-balance")}</Text>
                                <Text size="xl" fw={700}>
                                  ${billing.wallet.balance_usd} USD
                                </Text>
                                <Text size="xs" c="dimmed">
                                  {parseFloat(billing.wallet.balance).toLocaleString(undefined, { maximumFractionDigits: 2 })} {billing.wallet.unit_name}
                                  {" · "}1 USD = {billing.wallet.one_usd_is.toLocaleString()} {billing.wallet.unit_name}
                                </Text>
                              </Stack>
                              {billing.subscription?.plan.credits_limit_usd && (
                                <Text size="sm" c="dimmed">
                                  / ${billing.subscription.plan.credits_limit_usd} USD {t("included")}
                                </Text>
                              )}
                            </Group>

                            {/* Progress bar */}
                            {billing.subscription?.plan.credits_limit_usd && (
                              <Box
                                style={{
                                  height: 8,
                                  borderRadius: 4,
                                  background: "var(--mantine-color-dark-4)",
                                  overflow: "hidden",
                                }}
                              >
                                <Box
                                  style={{
                                    height: "100%",
                                    borderRadius: 4,
                                    width: `${Math.min(
                                      100,
                                      (parseFloat(billing.wallet.balance_usd) /
                                        parseFloat(billing.subscription.plan.credits_limit_usd)) * 100
                                    )}%`,
                                    background: parseFloat(billing.wallet.balance_usd) /
                                      parseFloat(billing.subscription.plan.credits_limit_usd) < 0.2
                                      ? "var(--mantine-color-red-5)"
                                      : "var(--mantine-color-blue-5)",
                                    transition: "width 0.3s ease",
                                  }}
                                />
                              </Box>
                            )}
                          </Stack>
                        )}
                      </Card>

                      {/* ── Plan selector ── */}
                      <Title order={5} mt="sm">{t("choose-a-plan")}</Title>
                      <Group grow align="stretch">
                        {/* Organization / Business plan */}
                        <Card withBorder p="lg" style={{ position: "relative" }}>
                          {billing?.subscription?.plan.slug === "organization" && billing.subscription.is_active && (
                            <Badge color="green" style={{ position: "absolute", top: 12, right: 12 }}>
                              {t("current-plan")}
                            </Badge>
                          )}
                          <Stack gap="xs">
                            <Group gap="xs">
                              <IconCreditCard size={20} />
                              <Text fw={700}>Business</Text>
                            </Group>
                            <Text size="sm" c="dimmed">{t("plan-organization-desc")}</Text>
                            <Button
                              mt="sm"
                              fullWidth
                              disabled={
                                billing?.subscription?.plan.slug === "organization" &&
                                billing?.subscription?.is_active
                              }
                              loading={checkoutLoading === "organization"}
                              onClick={() => handleSubscribe("organization")}
                            >
                              {checkoutLoading === "organization"
                                ? t("redirecting-to-stripe")
                                : t("upgrade-to-business")}
                            </Button>
                          </Stack>
                        </Card>

                        {/* Pay As You Go plan */}
                        <Card withBorder p="lg" style={{ position: "relative" }}>
                          {billing?.subscription?.plan.slug === "pay_as_you_go" && billing.subscription.is_active && (
                            <Badge color="green" style={{ position: "absolute", top: 12, right: 12 }}>
                              {t("current-plan")}
                            </Badge>
                          )}
                          <Stack gap="xs">
                            <Group gap="xs">
                              <IconCreditCard size={20} />
                              <Text fw={700}>Pay As You Go</Text>
                            </Group>
                            <Text size="sm" c="dimmed">{t("plan-payg-desc")}</Text>
                            <Button
                              mt="sm"
                              fullWidth
                              variant="outline"
                              disabled={
                                billing?.subscription?.plan.slug === "pay_as_you_go" &&
                                billing?.subscription?.is_active
                              }
                              loading={checkoutLoading === "pay_as_you_go"}
                              onClick={() => handleSubscribe("pay_as_you_go")}
                            >
                              {checkoutLoading === "pay_as_you_go"
                                ? t("redirecting-to-stripe")
                                : t("subscribe-pay-as-you-go")}
                            </Button>
                          </Stack>
                        </Card>
                      </Group>

                      {/* ── Buy credits (top-up) ── */}
                      <Card withBorder p="lg" mt="sm">
                        <Stack gap="sm">
                          <Title order={5}>{t("buy-credits-title")}</Title>
                          <Text size="sm" c="dimmed">{t("buy-credits-desc")}</Text>

                          {/* Preset amounts */}
                          <Group gap="xs">
                            {[10, 25, 50, 100].map((usd) => (
                              <Button
                                key={usd}
                                size="xs"
                                variant={creditAmount === usd ? "filled" : "outline"}
                                onClick={() => setCreditAmount(usd)}
                              >
                                ${usd}
                              </Button>
                            ))}
                          </Group>

                          {/* Custom amount slider */}
                          <Group align="center" gap="md">
                            <input
                              type="range"
                              min={10}
                              max={100}
                              step={5}
                              value={creditAmount}
                              onChange={(e) => setCreditAmount(Number(e.target.value))}
                              style={{ flex: 1 }}
                            />
                            <Text fw={700} w={70} ta="right">${creditAmount} USD</Text>
                          </Group>

                          {billing?.wallet && (
                            <Text size="xs" c="dimmed">
                              {t("credits-after-purchase", {
                                units: (creditAmount * billing.wallet.one_usd_is).toLocaleString(),
                              })}
                            </Text>
                          )}

                          <Button
                            loading={buyingCredits}
                            onClick={handleBuyCredits}
                            leftSection={<IconCreditCard size={16} />}
                          >
                            {buyingCredits ? t("buy-credits-loading") : t("buy-credits-submit")}
                          </Button>
                        </Stack>
                      </Card>
                    </>
                  )}
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
                    <Group key={flag.name} gap={6} wrap="nowrap">
                      <Checkbox
                        label={t(`ff-${flag.name}`)}
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
                        styles={{ body: { alignItems: "center" } }}
                      />
                      <Tooltip
                        label={t(`ff-${flag.name}-desc`)}
                        multiline
                        w={260}
                        withArrow
                        position="right"
                      >
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          size={18}
                          radius="xl"
                          style={{ cursor: "help" }}
                        >
                          <IconQuestionMark size={12} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
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

      {/* ── Member action confirmation modal ── */}
      <Modal
        opened={!!memberAction}
        onClose={closeMemberAction}
        title={
          memberAction?.action === "remove"
            ? t("remove-member")
            : memberAction?.action === "deactivate"
              ? t("deactivate-member")
              : t("reactivate-member")
        }
        centered
        size="sm"
      >
        {memberAction && (
          <Stack gap="md">
            <Text size="sm">
              {memberAction.action === "remove"
                ? t("confirm-remove-member-description", {
                    name:
                      memberAction.member.profile_name ||
                      memberAction.member.username ||
                      memberAction.member.email,
                  })
                : memberAction.action === "deactivate"
                  ? t("confirm-deactivate-member-description", {
                      name:
                        memberAction.member.profile_name ||
                        memberAction.member.username ||
                        memberAction.member.email,
                    })
                  : t("confirm-reactivate-member-description", {
                      name:
                        memberAction.member.profile_name ||
                        memberAction.member.username ||
                        memberAction.member.email,
                    })}
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={closeMemberAction}>
                {t("cancel")}
              </Button>
              <Button
                color={memberAction.action === "remove" ? "red" : memberAction.action === "deactivate" ? "yellow" : "green"}
                loading={memberActionLoading}
                onClick={confirmMemberAction}
              >
                {memberAction.action === "remove"
                  ? t("remove")
                  : memberAction.action === "deactivate"
                    ? t("deactivate")
                    : t("reactivate")}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      {/* ── Create member modal ── */}
      <Modal
        opened={createMemberOpened}
        onClose={() => {
          setCreateMemberOpened(false);
          setCreateMemberForm({ username: "", email: "", password: "", name: "", bio: "", expires_at: "" });
        }}
        title={t("create-member")}
        centered
      >
        <Stack gap="md">
          <TextInput
            label={t("username")}
            required
            value={createMemberForm.username}
            onChange={(e) => setCreateMemberForm({ ...createMemberForm, username: e.currentTarget.value })}
          />
          <TextInput
            label={t("email")}
            type="email"
            required
            value={createMemberForm.email}
            onChange={(e) => setCreateMemberForm({ ...createMemberForm, email: e.currentTarget.value })}
          />
          <TextInput
            label={t("password")}
            type="password"
            required
            value={createMemberForm.password}
            onChange={(e) => setCreateMemberForm({ ...createMemberForm, password: e.currentTarget.value })}
          />
          <TextInput
            label={t("name-optional")}
            value={createMemberForm.name}
            onChange={(e) => setCreateMemberForm({ ...createMemberForm, name: e.currentTarget.value })}
          />
          <Textarea
            label={t("notes-bio-optional")}
            description={t("notes-bio-description")}
            value={createMemberForm.bio}
            onChange={(e) => setCreateMemberForm({ ...createMemberForm, bio: e.currentTarget.value })}
            autosize
            minRows={2}
          />
          <TextInput
            label={t("expires-at-optional")}
            type="datetime-local"
            value={createMemberForm.expires_at}
            onChange={(e) => setCreateMemberForm({ ...createMemberForm, expires_at: e.currentTarget.value })}
            description={t("expires-at-description")}
          />
          <Group>
            <Button onClick={handleCreateMember} loading={createMemberLoading} flex={1}>
              {t("create")}
            </Button>
            <Button
              variant="default"
              onClick={() => {
                setCreateMemberOpened(false);
                setCreateMemberForm({ username: "", email: "", password: "", name: "", bio: "", expires_at: "" });
              }}
            >
              {t("cancel")}
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* ── Edit member modal ── */}
      <Modal
        opened={!!editingMember}
        onClose={() => setEditingMember(null)}
        title={`${t("edit-member")}: ${editingMember?.profile_name || editingMember?.username || ""}`}
        centered
      >
        {editingMember && (
          <Stack gap="md">
            <TextInput
              label={t("name")}
              value={editMemberForm.name}
              onChange={(e) => setEditMemberForm({ ...editMemberForm, name: e.currentTarget.value })}
            />
            <Textarea
              label={t("notes-bio")}
              description={t("notes-bio-description")}
              value={editMemberForm.bio}
              onChange={(e) => setEditMemberForm({ ...editMemberForm, bio: e.currentTarget.value })}
              autosize
              minRows={2}
            />
            <TextInput
              label={t("expires-at")}
              type="datetime-local"
              value={editMemberForm.expires_at}
              onChange={(e) => setEditMemberForm({ ...editMemberForm, expires_at: e.currentTarget.value })}
              description={t("expires-at-clear-description")}
            />
            <Group>
              <Button onClick={handleEditMember} loading={editMemberLoading} flex={1}>
                {t("save")}
              </Button>
              <Button variant="default" onClick={() => setEditingMember(null)}>
                {t("cancel")}
              </Button>
            </Group>
          </Stack>
        )}
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
