import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  assignRoleToMember,
  createOrganizationRole,
  deleteOrganizationRole,
  getFeatureFlagNames,
  getOrganizationMembers,
  getOrganizationRoles,
  getUserOrganizations,
  removeRoleAssignment,
  updateOrganizationRole,
} from "../../modules/apiCalls";
import { titlelify } from "../../modules/utils";
import { TOrganization, TOrganizationMember, TOrganizationRole } from "../../types";
import { useTranslation } from "react-i18next";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import toast from "react-hot-toast";
import "./page.css";

export default function OrganizationPage() {
  const { chatState, toggleSidebar, setUser, setOpenedModals } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
    setUser: s.setUser,
    setOpenedModals: s.setOpenedModals,
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

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getUserOrganizations();
        setOrgs(data.filter((o) => o.is_owner || o.can_manage));
      } catch {
        setOrgs([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const org = orgs[0] ?? null;

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

  const openSettings = () => {
    setOpenedModals({ action: "add", name: "settings" });
    toggleSidebar();
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
              svg={SVGS.burger}
            />
          </div>
        )}
        <div className="max-w-2xl mx-auto px-4">
          <div className="org-header">
            <h1 className="text-2xl md:text-4xl font-bold mb-4 md:mb-8 text-center text-white tracking-tight">
              {t("manage-organization")}
            </h1>
          </div>

          {!org ? (
            <>
              {!chatState.isSidebarOpened && (
                <div className="absolute top-6 left-6 z-10">
                  <SvgButton
                    extraClass="pressable active-on-hover"
                    onClick={toggleSidebar}
                    svg={SVGS.burger}
                  />
                </div>
              )}
              <div className="org-empty-state">
              <p>{t("no-organization-to-manage")}</p>
              <p className="text-sm">{t("create-or-join-organization-in-settings")}</p>
              <button
                type="button"
                className={`mt-4 px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 mx-auto ${
                  hoveredButton === "settings"
                    ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                    : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
                }`}
                onMouseEnter={() => setHoveredButton("settings")}
                onMouseLeave={() => setHoveredButton(null)}
                onClick={openSettings}
              >
                <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.settings}</span>
                {t("settings")}
              </button>
            </div>
            </>
          ) : (
            <>
              <div className="org-card">
                <div className="flex items-center gap-4 mb-4">
                  {org.logo_url && (
                    <img
                      src={org.logo_url}
                      alt={org.name}
                      className="rounded w-14 h-14 object-cover"
                    />
                  )}
                  <div>
                    <h2>{org.name}</h2>
                    {org.description && (
                      <p className="text-sm text-[rgb(156,156,156)] mt-1">{org.description}</p>
                    )}
                  </div>
                </div>
              </div>

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
                    <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.copy}</span>
                    {t("copy")}
                  </button>
                </div>
              </div>

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
                      <span className="[&>svg]:w-4 [&>svg]:h-4">{SVGS.plus}</span>
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
