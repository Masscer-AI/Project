import React, { useState, useEffect, useRef } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  assignRoleToMember,
  createOrganization,
  createOrganizationRole,
  deleteOrganization,
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
import { TOrganization, TOrganizationMember, TOrganizationRole } from "../../types";
import { useTranslation } from "react-i18next";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import toast from "react-hot-toast";
import { Icon } from "../../components/Icon/Icon";
import "./page.css";

export default function OrganizationPage() {
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));
  const { t } = useTranslation();
  const [orgs, setOrgs] = useState<TOrganization[]>([]);
  const [members, setMembers] = useState<TOrganizationMember[]>([]);
  const [roles, setRoles] = useState<TOrganizationRole[]>([]);
  const [featureFlagNames, setFeatureFlagNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [showRoleForm, setShowRoleForm] = useState(false);
  const [editingRole, setEditingRole] = useState<TOrganizationRole | null>(null);
  const [roleForm, setRoleForm] = useState({ name: "", description: "", capabilities: [] as string[] });
  const [assigningUserId, setAssigningUserId] = useState<number | null>(null);

  // Organization settings state
  const [editingOrgSettings, setEditingOrgSettings] = useState(false);
  const [orgForm, setOrgForm] = useState({ name: "", description: "" });
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [deleteLogo, setDeleteLogo] = useState(false);
  const [savingOrg, setSavingOrg] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);

  // Create organization state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", description: "" });
  const [creating, setCreating] = useState(false);

  const loadOrgs = async () => {
    try {
      const data = await getUserOrganizations();
      setOrgs(data.filter((o) => o.is_owner || o.can_manage));
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
      setOrgForm({ name: org.name, description: org.description || "" });
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
    getFeatureFlagNames().then(setFeatureFlagNames).catch(() => setFeatureFlagNames([]));
  }, []);

  const inviteUrl = org ? `${window.location.origin}/signup?orgId=${org.id}` : "";

  const reloadMembers = () => {
    if (org?.id) getOrganizationMembers(org.id).then(setMembers).catch(() => setMembers([]));
  };

  const reloadRoles = () => {
    if (org?.id) getOrganizationRoles(org.id).then(setRoles).catch(() => setRoles([]));
  };

  // Create organization
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
      toast.error(e?.response?.data?.detail || t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
      setCreating(false);
    }
  };

  // Save organization settings
  const handleSaveOrgSettings = async () => {
    if (!org?.id || !orgForm.name.trim()) return;
    setSavingOrg(true);
    const tid = toast.loading(t("loading"));
    try {
      let options: { logoFile?: File; deleteLogo: boolean } | undefined;
      if (logoFile) {
        options = { logoFile, deleteLogo: false };
      } else if (deleteLogo) {
        options = { deleteLogo: true };
      }

      await updateOrganization(org.id, orgForm, options);
      toast.success(t("organization-updated"));
      setEditingOrgSettings(false);
      setLogoFile(null);
      setDeleteLogo(false);
      await loadOrgs();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t("error-updating-organization"));
    } finally {
      toast.dismiss(tid);
      setSavingOrg(false);
    }
  };

  // Delete organization
  const handleDeleteOrg = async () => {
    if (!org?.id || !window.confirm(t("sure-this-action-is-irreversible"))) return;
    const tid = toast.loading(t("loading"));
    try {
      await deleteOrganization(org.id);
      toast.success(t("organization-deleted"));
      await loadOrgs();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
    }
  };

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
      setShowRoleForm(false);
      setEditingRole(null);
      setRoleForm({ name: "", description: "", capabilities: [] });
      reloadRoles();
    } catch (e: any) {
      toast.error(e?.response?.data?.name?.[0] || e?.response?.data?.detail || t("an-error-occurred"));
    } finally {
      toast.dismiss(tid);
    }
  };

  const handleDeleteRole = async (role: TOrganizationRole) => {
    if (!org?.id || !window.confirm(t("confirm-delete-role"))) return;
    const tid = toast.loading(t("loading"));
    try {
      await deleteOrganizationRole(org.id, role.id);
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
        await assignRoleToMember(org.id, { user_id: userId, role_id: roleId });
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
    setShowRoleForm(true);
  };

  const openEditRole = (role: TOrganizationRole) => {
    setEditingRole(role);
    setRoleForm({
      name: role.name,
      description: role.description || "",
      capabilities: role.capabilities || [],
    });
    setShowRoleForm(true);
  };

  const copyInviteLink = () => {
    if (!inviteUrl) return;
    navigator.clipboard.writeText(inviteUrl);
    toast.success(t("copied-to-clipboard"));
  };

  if (loading) {
    return (
      <main className="d-flex pos-relative h-viewport">
        <Sidebar />
        <div className="org-container">
          <div className="max-w-2xl mx-auto px-4 py-12 text-center text-[rgb(156,156,156)]">
            {t("loading")}
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div className="org-container relative">
        {!chatState.isSidebarOpened && (
          <div className="absolute top-6 left-6 z-10">
            <SvgButton
              extraClass="pressable active-on-hover"
              onClick={toggleSidebar}
              svg={<Icon name="Menu" size={20} />}
            />
          </div>
        )}
        <div className="max-w-2xl mx-auto px-4">
          <div className="org-header">
            <h1 className="text-2xl md:text-4xl font-bold mb-4 md:mb-8 text-center text-white tracking-tight">
              {org ? t("manage-organization") : t("organization")}
            </h1>
          </div>

          {!org ? (
            // No organization - show create form
            <div className="org-card">
              {!showCreateForm ? (
                <div className="text-center py-8">
                  <p className="text-[rgb(156,156,156)] mb-4">{t("no-organizations-message")}</p>
                  <button
                    type="button"
                    className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 mx-auto ${
                      hoveredButton === "create-org"
                        ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                        : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
                    }`}
                    onMouseEnter={() => setHoveredButton("create-org")}
                    onMouseLeave={() => setHoveredButton(null)}
                    onClick={() => setShowCreateForm(true)}
                  >
                    <Icon name="Plus" size={20} />
                    {t("create-organization")}
                  </button>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <h2 className="text-white font-semibold">{t("create-organization")}</h2>
                  <div className="flex flex-col gap-2">
                    <label className="text-[rgb(156,156,156)] text-sm">{t("organization-name")}</label>
                    <input
                      type="text"
                      value={createForm.name}
                      onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                      placeholder={t("name-for-your-organization")}
                      className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-[rgb(156,156,156)] text-sm">{t("describe-your-organization")}</label>
                    <textarea
                      value={createForm.description}
                      onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                      placeholder={t("describe-your-organization")}
                      rows={3}
                      className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)] resize-none"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleCreateOrg}
                      disabled={creating}
                      className={`flex-1 px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                        hoveredButton === "submit-create"
                          ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                          : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
                      }`}
                      onMouseEnter={() => setHoveredButton("submit-create")}
                      onMouseLeave={() => setHoveredButton(null)}
                    >
                      {t("create")}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowCreateForm(false);
                        setCreateForm({ name: "", description: "" });
                      }}
                      className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
                        hoveredButton === "cancel-create"
                          ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                          : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
                      }`}
                      onMouseEnter={() => setHoveredButton("cancel-create")}
                      onMouseLeave={() => setHoveredButton(null)}
                    >
                      {t("cancel")}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Organization Settings Card */}
              <div className="org-card">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-white font-semibold m-0">{t("organization-settings")}</h2>
                  {org.is_owner && !editingOrgSettings && (
                    <button
                      type="button"
                      className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
                        hoveredButton === "edit-org"
                          ? "bg-white text-gray-800"
                          : "bg-[rgba(35,33,39,0.5)] text-white border-white/20 hover:bg-[rgba(35,33,39,0.8)]"
                      }`}
                      onMouseEnter={() => setHoveredButton("edit-org")}
                      onMouseLeave={() => setHoveredButton(null)}
                      onClick={() => setEditingOrgSettings(true)}
                    >
                      <Icon name="Pencil" size={16} />
                      {t("edit")}
                    </button>
                  )}
                </div>

                {!editingOrgSettings ? (
                  // View mode
                  <div className="flex items-center gap-4">
                    {org.logo_url ? (
                      <img
                        src={org.logo_url}
                        alt={org.name}
                        className="rounded w-16 h-16 object-cover"
                      />
                    ) : (
                      <div className="rounded w-16 h-16 bg-[rgba(255,255,255,0.05)] flex items-center justify-center text-[rgb(156,156,156)] text-xs">
                        {t("no-logo")}
                      </div>
                    )}
                    <div>
                      <h3 className="text-white font-semibold m-0">{org.name}</h3>
                      {org.description && (
                        <p className="text-sm text-[rgb(156,156,156)] mt-1 m-0">{org.description}</p>
                      )}
                    </div>
                  </div>
                ) : (
                  // Edit mode
                  <div className="flex flex-col gap-4">
                    {/* Logo */}
                    <div className="flex flex-col gap-2">
                      <label className="text-[rgb(156,156,156)] text-sm">{t("organization-logo")}</label>
                      <div className="flex items-center gap-4 flex-wrap">
                        {(org.logo_url && !deleteLogo && !logoFile) ? (
                          <img
                            src={org.logo_url}
                            alt={org.name}
                            className="rounded w-16 h-16 object-cover"
                          />
                        ) : logoFile ? (
                          <LogoPreview file={logoFile} />
                        ) : (
                          <div className="rounded w-16 h-16 bg-[rgba(255,255,255,0.05)] flex items-center justify-center text-[rgb(156,156,156)] text-xs">
                            {t("no-logo")}
                          </div>
                        )}
                        <div className="flex gap-2 flex-wrap">
                          <input
                            ref={logoInputRef}
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              if (f) {
                                setLogoFile(f);
                                setDeleteLogo(false);
                              }
                              e.target.value = "";
                            }}
                          />
                          <button
                            type="button"
                            className="px-3 py-1.5 rounded-full text-sm cursor-pointer border bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
                            onClick={() => logoInputRef.current?.click()}
                          >
                            {t("change-logo")}
                          </button>
                          {((org.logo_url || logoFile) && !deleteLogo) && (
                            <button
                              type="button"
                              className="px-3 py-1.5 rounded-full text-sm cursor-pointer border border-red-500/50 text-red-400 hover:bg-red-500/20"
                              onClick={() => {
                                setDeleteLogo(true);
                                setLogoFile(null);
                              }}
                            >
                              {t("remove-logo")}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Name */}
                    <div className="flex flex-col gap-2">
                      <label className="text-[rgb(156,156,156)] text-sm">{t("organization-name")}</label>
                      <input
                        type="text"
                        value={orgForm.name}
                        onChange={(e) => setOrgForm({ ...orgForm, name: e.target.value })}
                        className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
                      />
                    </div>

                    {/* Description */}
                    <div className="flex flex-col gap-2">
                      <label className="text-[rgb(156,156,156)] text-sm">{t("describe-your-organization")}</label>
                      <textarea
                        value={orgForm.description}
                        onChange={(e) => setOrgForm({ ...orgForm, description: e.target.value })}
                        rows={3}
                        className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)] resize-none"
                      />
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 flex-wrap">
                      <button
                        type="button"
                        onClick={handleSaveOrgSettings}
                        disabled={savingOrg}
                        className={`flex-1 px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                          hoveredButton === "save-org"
                            ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                            : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
                        }`}
                        onMouseEnter={() => setHoveredButton("save-org")}
                        onMouseLeave={() => setHoveredButton(null)}
                      >
                        <Icon name="Save" size={16} />
                        {t("save")}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingOrgSettings(false);
                          setOrgForm({ name: org.name, description: org.description || "" });
                          setLogoFile(null);
                          setDeleteLogo(false);
                        }}
                        className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
                          hoveredButton === "cancel-org"
                            ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                            : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
                        }`}
                        onMouseEnter={() => setHoveredButton("cancel-org")}
                        onMouseLeave={() => setHoveredButton(null)}
                      >
                        {t("cancel")}
                      </button>
                      <button
                        type="button"
                        onClick={handleDeleteOrg}
                        className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                          hoveredButton === "delete-org"
                            ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                            : "bg-[#dc2626] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#b91c1c]"
                        }`}
                        onMouseEnter={() => setHoveredButton("delete-org")}
                        onMouseLeave={() => setHoveredButton(null)}
                      >
                        <Icon name="Trash2" size={16} />
                        {t("delete")}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Invite Link */}
              <div className="org-card">
                <h2>{t("invite-link")}</h2>
                <p className="text-sm text-[rgb(156,156,156)] mb-3">{t("invite-link-description")}</p>
                <div className="org-invite-link-row">
                  <input type="text" readOnly value={inviteUrl} />
                  <button
                    type="button"
                    className={`px-4 py-2.5 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 whitespace-nowrap ${
                      hoveredButton === "copy"
                        ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                        : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
                    }`}
                    onMouseEnter={() => setHoveredButton("copy")}
                    onMouseLeave={() => setHoveredButton(null)}
                    onClick={copyInviteLink}
                  >
                    <Icon name="Copy" size={20} />
                    {t("copy")}
                  </button>
                </div>
              </div>

              {/* Roles */}
              <div className="org-card">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <h2 className="m-0">{t("roles")}</h2>
                  {!showRoleForm && (
                    <button
                      type="button"
                      className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
                        hoveredButton === "create-role"
                          ? "bg-white text-gray-800"
                          : "bg-[rgba(35,33,39,0.5)] text-white border-white/20 hover:bg-[rgba(35,33,39,0.8)]"
                      }`}
                      onMouseEnter={() => setHoveredButton("create-role")}
                      onMouseLeave={() => setHoveredButton(null)}
                      onClick={openCreateRole}
                    >
                      <Icon name="Plus" size={16} />
                      {t("create-role")}
                    </button>
                  )}
                </div>
                {showRoleForm && (
                  <div className="mt-4 p-4 rounded-xl bg-white/5 border border-white/10 flex flex-col gap-3">
                    <input
                      type="text"
                      className="w-full px-3 py-2 rounded-lg border border-white/20 bg-white/5 text-white placeholder-white/40"
                      placeholder={t("role-name-placeholder")}
                      value={roleForm.name}
                      onChange={(e) => setRoleForm((f) => ({ ...f, name: e.target.value }))}
                    />
                    <textarea
                      className="w-full px-3 py-2 rounded-lg border border-white/20 bg-white/5 text-white placeholder-white/40 min-h-[80px]"
                      placeholder={t("role-description-placeholder")}
                      value={roleForm.description}
                      onChange={(e) => setRoleForm((f) => ({ ...f, description: e.target.value }))}
                    />
                    <div>
                      <label className="text-sm text-white/70 block mb-2">{t("capabilities")}</label>
                      <div className="flex flex-wrap gap-2">
                        {featureFlagNames.map((flag) => (
                          <label key={flag} className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={roleForm.capabilities.includes(flag)}
                              onChange={(e) =>
                                setRoleForm((f) => ({
                                  ...f,
                                  capabilities: e.target.checked
                                    ? [...f.capabilities, flag]
                                    : f.capabilities.filter((c) => c !== flag),
                                }))
                              }
                              className="rounded"
                            />
                            <span className="text-sm text-white/80">{titlelify(flag)}</span>
                          </label>
                        ))}
                        {featureFlagNames.length === 0 && (
                          <span className="text-sm text-white/50">{t("no-capabilities-available")}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="px-4 py-2 rounded-full text-sm bg-[rgba(110,91,255,0.6)] text-white border-0 cursor-pointer hover:bg-[rgba(110,91,255,0.8)]"
                        onClick={handleSaveRole}
                      >
                        {editingRole ? t("update") : t("create")}
                      </button>
                      <button
                        type="button"
                        className="px-4 py-2 rounded-full text-sm bg-white/10 text-white border border-white/20 cursor-pointer hover:bg-white/20"
                        onClick={() => {
                          setShowRoleForm(false);
                          setEditingRole(null);
                          setRoleForm({ name: "", description: "", capabilities: [] });
                        }}
                      >
                        {t("cancel")}
                      </button>
                    </div>
                  </div>
                )}
                {loadingRoles ? (
                  <div className="org-members-placeholder mt-4">{t("loading")}</div>
                ) : roles.length === 0 && !showRoleForm ? (
                  <div className="org-members-placeholder mt-4">{t("no-roles-yet")}</div>
                ) : (
                  <ul className="list-none p-0 m-0 mt-4 flex flex-col gap-2">
                    {roles.map((role) => (
                      <li
                        key={role.id}
                        className="flex items-center justify-between gap-3 py-2 px-3 rounded-lg bg-white/5 border border-white/10"
                      >
                        <div>
                          <span className="font-medium text-white">{role.name}</span>
                          {role.description && (
                            <p className="text-sm text-white/60 m-0 mt-0.5">{role.description}</p>
                          )}
                          {role.capabilities?.length > 0 && (
                            <p className="text-xs text-white/50 mt-1">
                              {t("capabilities")}: {role.capabilities.map(titlelify).join(", ")}
                            </p>
                          )}
                        </div>
                        <div className="flex gap-2 shrink-0">
                          <button
                            type="button"
                            className="px-3 py-1.5 rounded-full text-xs bg-white/10 text-white border border-white/20 hover:bg-white/20"
                            onClick={() => openEditRole(role)}
                          >
                            {t("edit")}
                          </button>
                          <button
                            type="button"
                            className="px-3 py-1.5 rounded-full text-xs bg-red-500/20 text-red-300 border border-red-500/30 hover:bg-red-500/30"
                            onClick={() => handleDeleteRole(role)}
                          >
                            {t("delete")}
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Members */}
              <div className="org-card">
                <h2>{t("members")}</h2>
                {loadingMembers ? (
                  <div className="org-members-placeholder">{t("loading")}</div>
                ) : members.length === 0 ? (
                  <div className="org-members-placeholder">{t("no-members-yet")}</div>
                ) : (
                  <ul className="list-none p-0 m-0 flex flex-col gap-2">
                    {members.map((m) => (
                      <li
                        key={m.id}
                        className="flex items-center justify-between gap-3 py-2 px-3 rounded-lg bg-white/5 border border-white/10"
                      >
                        <div className="min-w-0 flex-1">
                          <span className="font-medium text-[var(--font-color,#fff)] block truncate">
                            {m.profile_name || m.username || m.email || String(m.id)}
                          </span>
                          <span className="text-sm text-[rgb(156,156,156)] truncate block">
                            {m.email}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0 flex-wrap">
                          {m.is_owner && (
                            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-[rgba(110,91,255,0.3)] text-[rgba(200,190,255,1)]">
                              {t("owner")}
                            </span>
                          )}
                          {org?.id && (
                            <select
                              className="text-sm px-2 py-1 rounded-lg bg-white/10 border border-white/20 text-white cursor-pointer min-w-[120px]"
                              value={m.current_role?.id ?? ""}
                              onChange={(e) => {
                                const v = e.target.value;
                                handleAssignRole(m.id, v || null);
                              }}
                              disabled={assigningUserId === m.id}
                            >
                              <option value="">— {t("no-role")} —</option>
                              {roles.map((r) => (
                                <option key={r.id} value={r.id}>
                                  {r.name}
                                </option>
                              ))}
                            </select>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

// Helper component for logo preview
const LogoPreview = ({ file }: { file: File }) => {
  const [src, setSrc] = useState<string>("");
  useEffect(() => {
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return (
    <img
      src={src}
      alt="Preview"
      className="rounded w-16 h-16 object-cover"
    />
  );
};
