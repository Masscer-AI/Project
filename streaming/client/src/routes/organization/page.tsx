import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  assignRoleToMember,
  buyCredits,
  createBillingPortalSession,
  createCheckoutSession,
  createOrganization,
  createOrganizationInvite,
  createOrganizationRole,
  deactivateOrganizationMember,
  deleteOrganizationRole,
  getFeatureFlagNames,
  getOrganizationBilling,
  getOrganizationMembers,
  getOrganizationInvites,
  getOrganizationRoles,
  getUserOrganizations,
  reactivateOrganizationSubscription,
  removeOrganizationMember,
  removeRoleAssignment,
  revokeOrganizationInvite,
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
  TOrganizationInvite,
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
  IconDatabase,
} from "@tabler/icons-react";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { DataGovernanceTab } from "./DataGovernanceTab";

const CREDIT_PACKAGES = [
  { amountUsd: 50, creditsUsd: 40 },
  { amountUsd: 100, creditsUsd: 80 },
  { amountUsd: 200, creditsUsd: 160 },
] as const;

const ORGANIZATION_TAB_VALUES = [
  "settings",
  "roles",
  "members",
  "billing",
  "data",
] as const;

export type OrganizationTab = (typeof ORGANIZATION_TAB_VALUES)[number];

/** Maps URL ?activeTab= to organization page section (default: settings). */
export function parseOrganizationActiveTab(
  searchParams: URLSearchParams
): OrganizationTab {
  const raw = (searchParams.get("activeTab") || "").toLowerCase();
  if ((ORGANIZATION_TAB_VALUES as readonly string[]).includes(raw)) {
    return raw as OrganizationTab;
  }
  return "settings";
}

export default function OrganizationPage() {
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const organizationTab = parseOrganizationActiveTab(searchParams);

  const setOrganizationTab = (tab: OrganizationTab) => {
    const next = new URLSearchParams(searchParams);
    if (tab === "settings") {
      next.delete("activeTab");
    } else {
      next.set("activeTab", tab);
    }
    setSearchParams(next);
  };

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
  const [billingPortalLoading, setBillingPortalLoading] = useState(false);
  const [reactivatingSubscription, setReactivatingSubscription] = useState(false);
  const [creditAmount, setCreditAmount] = useState<number>(50);
  const [buyingCredits, setBuyingCredits] = useState(false);
  const canUseOneDollarPackage =
    useIsFeatureEnabled("one-dolar-credits-package") === true;
  const availableCreditPackages = canUseOneDollarPackage
    ? ([{ amountUsd: 1, creditsUsd: 0.8 }, ...CREDIT_PACKAGES] as const)
    : CREDIT_PACKAGES;

  const getBillingCycleLabel = (interval?: string) => {
    switch (interval) {
      case "monthly":
        return t("billing-cycle-monthly");
      case "quarterly":
        return t("billing-cycle-quarterly");
      case "yearly":
        return t("billing-cycle-yearly");
      case "one_time":
        return t("billing-cycle-one-time");
      case "custom":
        return t("billing-cycle-custom");
      default:
        return t("billing-cycle-monthly");
    }
  };

  const renderSubscriptionPrice = (subscription: NonNullable<TOrganizationBilling["subscription"]>) => {
    const raw = subscription.display_monthly_price_usd ?? subscription.plan.monthly_price_usd ?? "0";
    const amount = Number.parseFloat(raw);
    if (!Number.isFinite(amount) || amount === 0) {
      return `${t("free")} (${getBillingCycleLabel(subscription.billing_interval)})`;
    }
    return `$${raw} USD (${getBillingCycleLabel(subscription.billing_interval)})`;
  };

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

  const handleSubscribe = async (planSlug: "organization") => {
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

  const handleManageSubscription = async () => {
    if (!org?.id) return;
    setBillingPortalLoading(true);
    try {
      const { portal_url } = await createBillingPortalSession(org.id);
      window.location.href = portal_url;
    } catch {
      toast.error(t("billing-portal-error"));
    } finally {
      setBillingPortalLoading(false);
    }
  };

  const handleReactivateSubscription = async () => {
    if (!org?.id) return;
    setReactivatingSubscription(true);
    try {
      await reactivateOrganizationSubscription(org.id);
      toast.success(t("subscription-reactivated"));
      const refreshed = await getOrganizationBilling(org.id);
      setBilling(refreshed);
    } catch {
      toast.error(t("subscription-reactivate-error"));
    } finally {
      setReactivatingSubscription(false);
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

  // Invite member modal (email invite — user sets password via link)
  const [createMemberOpened, setCreateMemberOpened] = useState(false);
  const [createMemberForm, setCreateMemberForm] = useState({
    email: "",
    name: "",
    bio: "",
    expires_at: "",
  });
  const [createMemberLoading, setCreateMemberLoading] = useState(false);
  const [invites, setInvites] = useState<TOrganizationInvite[]>([]);
  const [loadingInvites, setLoadingInvites] = useState(false);

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

  useEffect(() => {
    const raw = searchParams.get("activeTab");
    if (!raw) return;
    if (parseOrganizationActiveTab(searchParams) !== raw.toLowerCase()) {
      const next = new URLSearchParams(searchParams);
      next.delete("activeTab");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const org = orgs[0] ?? null;
  const hasCustomSubscription = billing?.subscription?.plan?.slug === "custom";
  const hasActiveOrganizationPlan = Boolean(
    billing?.subscription?.is_active &&
    billing?.subscription?.plan?.slug === "organization"
  );
  const canSubscribeToStripePlan = !hasActiveOrganizationPlan && !hasCustomSubscription;
  const canBuyCredits = hasActiveOrganizationPlan && !hasCustomSubscription;

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
    if (!org?.id) {
      setInvites([]);
      return;
    }
    setLoadingInvites(true);
    getOrganizationInvites(org.id)
      .then(setInvites)
      .catch(() => setInvites([]))
      .finally(() => setLoadingInvites(false));
  }, [org?.id]);

  useEffect(() => {
    getFeatureFlagNames()
      .then(setFeatureFlagNames)
      .catch(() => setFeatureFlagNames([]));
  }, []);

  const reloadInvites = () => {
    if (org?.id)
      getOrganizationInvites(org.id)
        .then(setInvites)
        .catch(() => setInvites([]));
  };

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
    const { email, name, bio, expires_at } = createMemberForm;
    if (!email.trim()) {
      toast.error(t("email-required-hint"));
      return;
    }
    setCreateMemberLoading(true);
    const tid = toast.loading(t("loading"));
    try {
      await createOrganizationInvite(org.id, {
        email: email.trim(),
        name: name.trim() || undefined,
        bio: bio.trim() || undefined,
        expires_at: expires_at ? new Date(expires_at).toISOString() : null,
      });
      setCreateMemberOpened(false);
      setCreateMemberForm({ email: "", name: "", bio: "", expires_at: "" });
      toast.success(t("invite-sent-success"));
      reloadInvites();
    } catch (e: any) {
      toast.error(e?.response?.data?.error || e?.response?.data?.detail || t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
      setCreateMemberLoading(false);
    }
  };

  const handleRevokeInvite = async (invite: TOrganizationInvite) => {
    if (!org?.id) return;
    const tid = toast.loading(t("loading"));
    try {
      await revokeOrganizationInvite(org.id, invite.id);
      toast.success(t("invite-revoked"));
      reloadInvites();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
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
            <Tabs
              value={organizationTab}
              onChange={(v) => {
                if (v) setOrganizationTab(v as OrganizationTab);
              }}
              variant="outline"
            >
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
                <Tabs.Tab
                  value="data"
                  leftSection={<IconDatabase size={16} />}
                >
                  {t("data-governance-tab")}
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

                  {/* Pending email invitations */}
                  <Card withBorder p="lg">
                    <Group justify="space-between" mb="md">
                      <Title order={4}>{t("pending-invitations")}</Title>
                    </Group>
                    {loadingInvites ? (
                      <Stack align="center" py="sm">
                        <Loader color="violet" size="sm" />
                      </Stack>
                    ) : invites.filter((i) => i.status === "pending").length === 0 ? (
                      <Text size="sm" c="dimmed">
                        {t("no-pending-invitations")}
                      </Text>
                    ) : (
                      <Stack gap="sm">
                        {invites
                          .filter((i) => i.status === "pending")
                          .map((inv) => (
                            <Card key={inv.id} withBorder p="sm" style={{ background: "rgba(255,255,255,0.02)" }}>
                              <Group justify="space-between" wrap="nowrap" gap="sm">
                                <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
                                  <Text fw={500} truncate>
                                    {inv.email}
                                  </Text>
                                  <Text size="xs" c="dimmed">
                                    {t("invite-expires")}: {new Date(inv.invite_expires_at).toLocaleString()}
                                  </Text>
                                </Stack>
                                <Button
                                  variant="light"
                                  color="red"
                                  size="xs"
                                  onClick={() => handleRevokeInvite(inv)}
                                >
                                  {t("cancel-invite")}
                                </Button>
                              </Group>
                            </Card>
                          ))}
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
                        {t("invite-member")}
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
                              <Text size="sm" fw={600} w={160}>{t("price")}</Text>
                              <Text size="sm">{renderSubscriptionPrice(billing.subscription)}</Text>
                            </Group>
                            {billing.subscription.end_date && (
                              <Group gap="xs">
                                <Text size="sm" fw={600} w={160}>{t("expires")}</Text>
                                <Text size="sm">
                                  {new Date(billing.subscription.end_date).toLocaleDateString()}
                                </Text>
                              </Group>
                            )}
                            {billing.subscription.cancel_at_period_end && (
                              <Group gap="xs" align="center" mt={4}>
                                <Badge color="yellow" variant="light">
                                  {t("subscription-cancel-scheduled")}
                                </Badge>
                                <Text size="sm" c="dimmed">
                                  {t("subscription-cancel-scheduled-desc", {
                                    date: billing.subscription.cancel_at
                                      ? new Date(billing.subscription.cancel_at).toLocaleDateString()
                                      : (billing.subscription.end_date
                                          ? new Date(billing.subscription.end_date).toLocaleDateString()
                                          : "-"),
                                  })}
                                </Text>
                              </Group>
                            )}
                            {billing.subscription.payment_method === "stripe" && billing.subscription.is_active && (
                              <Group mt="sm">
                                <Button
                                  variant="default"
                                  onClick={handleManageSubscription}
                                  loading={billingPortalLoading}
                                >
                                  {billingPortalLoading
                                    ? t("redirecting-to-stripe")
                                    : t("manage-subscription")}
                                </Button>
                                {billing.subscription.cancel_at_period_end && (
                                  <Button
                                    variant="light"
                                    color="green"
                                    onClick={handleReactivateSubscription}
                                    loading={reactivatingSubscription}
                                  >
                                    {t("reactivate-subscription")}
                                  </Button>
                                )}
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
                                <Text size="xs" c="dimmed">
                                  {t("wallet-breakdown-subscription")}: ${billing.wallet.subscription_balance_usd} USD
                                  {" · "}
                                  {t("wallet-breakdown-purchased")}: ${billing.wallet.purchased_balance_usd} USD
                                </Text>
                              </Stack>
                              {billing.subscription?.plan.credits_limit_usd && (
                                <Text size="sm" c="dimmed">
                                  / ${billing.subscription.plan.credits_limit_usd} USD {t("included")}
                                </Text>
                              )}
                            </Group>

                            {!billing.subscription?.is_active
                              && parseFloat(billing.wallet.purchased_balance_usd) > 0 && (
                              <Text size="sm" c="orange">
                                {t("purchased-locked-after-expiry", {
                                  usd: billing.wallet.purchased_balance_usd,
                                })}
                              </Text>
                            )}

                            {/* Progress bar — subscription bucket vs plan included credits */}
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
                                      (parseFloat(billing.wallet.subscription_balance_usd) /
                                        parseFloat(billing.subscription.plan.credits_limit_usd)) * 100
                                    )}%`,
                                    background: parseFloat(billing.wallet.subscription_balance_usd) /
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
                      {canSubscribeToStripePlan ? (
                        <>
                          <Title order={5} mt="sm">{t("choose-a-plan")}</Title>
                          <Group grow align="stretch">
                            {/* Organization plan */}
                            <Card withBorder p="lg" style={{ position: "relative" }}>
                              <Stack gap="xs">
                                <Group gap="xs">
                                  <IconCreditCard size={20} />
                                  <Text fw={700}>Organization</Text>
                                </Group>
                                <Text size="sm" c="dimmed">{t("plan-organization-desc")}</Text>
                                <Button
                                  mt="sm"
                                  fullWidth
                                  loading={checkoutLoading === "organization"}
                                  onClick={() => handleSubscribe("organization")}
                                >
                                  {checkoutLoading === "organization"
                                    ? t("redirecting-to-stripe")
                                    : t("subscribe-organization")}
                                </Button>
                              </Stack>
                            </Card>
                          </Group>
                        </>
                      ) : (
                        hasCustomSubscription && (
                          <Text size="sm" c="dimmed" mt="sm">
                            {t("choose-a-plan-disabled-custom-subscription")}
                          </Text>
                        )
                      )}

                      {/* ── Buy credits (top-up) ── */}
                      <Card withBorder p="lg" mt="sm">
                        <Stack gap="sm">
                          <Title order={5}>{t("buy-credits-title")}</Title>
                          <Text size="sm" c="dimmed">
                            {canBuyCredits
                              ? t("buy-credits-desc")
                              : hasCustomSubscription
                                ? t("buy-credits-disabled-custom-subscription")
                                : t("buy-credits-disabled-no-subscription")}
                          </Text>

                          {/* Fixed package amounts */}
                          <Group gap="xs">
                            {availableCreditPackages.map(({ amountUsd, creditsUsd }) => (
                              <Button
                                key={amountUsd}
                                size="xs"
                                variant={creditAmount === amountUsd ? "filled" : "outline"}
                                onClick={() => setCreditAmount(amountUsd)}
                                disabled={!canBuyCredits}
                              >
                                ${amountUsd}
                                {" · "}
                                ${creditsUsd} {t("credits")}
                              </Button>
                            ))}
                          </Group>

                          {canBuyCredits && billing?.wallet && (
                            <Text size="xs" c="dimmed">
                              {t("credits-after-purchase", {
                                units: (
                                  parseFloat(billing.wallet.purchased_balance) +
                                  (availableCreditPackages.find((pkg) => pkg.amountUsd === creditAmount)?.creditsUsd ?? 0) *
                                  billing.wallet.one_usd_is
                                ).toLocaleString(undefined, { maximumFractionDigits: 0 }),
                              })}
                            </Text>
                          )}

                          <Button
                            loading={buyingCredits}
                            onClick={handleBuyCredits}
                            leftSection={<IconCreditCard size={16} />}
                            disabled={!canBuyCredits}
                          >
                            {buyingCredits ? t("buy-credits-loading") : t("buy-credits-submit")}
                          </Button>
                        </Stack>
                      </Card>
                    </>
                  )}
                </Stack>
              </Tabs.Panel>

              <Tabs.Panel value="data">
                {org?.id ? (
                  <DataGovernanceTab organizationId={org.id} />
                ) : null}
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
          setCreateMemberForm({ email: "", name: "", bio: "", expires_at: "" });
        }}
        title={t("invite-member")}
        centered
      >
        <Stack gap="md">
          <TextInput
            label={t("email")}
            type="email"
            required
            value={createMemberForm.email}
            onChange={(e) => setCreateMemberForm({ ...createMemberForm, email: e.currentTarget.value })}
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
          <Text size="xs" c="dimmed">
            {t("invite-member-email-hint")}
          </Text>
          <Group>
            <Button onClick={handleCreateMember} loading={createMemberLoading} flex={1}>
              {t("send-invite")}
            </Button>
            <Button
              variant="default"
              onClick={() => {
                setCreateMemberOpened(false);
                setCreateMemberForm({ email: "", name: "", bio: "", expires_at: "" });
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
