import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { 
  getAlertRules, 
  createAlertRule, 
  updateAlertRule, 
  deleteAlertRule 
} from "../../modules/apiCalls";
import { TConversationAlertRule } from "../../types";
import { ProtectedRoute } from "../../components/ProtectedRoute/ProtectedRoute";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import "./AlertRulesPage.css";

export default function AlertRulesPage() {
  const { chatState, startup } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [alertRules, setAlertRules] = useState<TConversationAlertRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<TConversationAlertRule | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    trigger: "",
    extractions: {} as Record<string, any>,
    scope: "all_conversations" as "all_conversations" | "selected_agents",
    enabled: true,
    notify_to: "all_staff" as "all_staff" | "selected_members",
  });

  useEffect(() => {
    startup();
    loadAlertRules();
  }, []);

  const loadAlertRules = async () => {
    try {
      setIsLoading(true);
      const data = await getAlertRules();
      setAlertRules(data);
    } catch (error) {
      console.error("Error loading alert rules:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingRule(null);
    setFormData({
      name: "",
      trigger: "",
      extractions: {},
      scope: "all_conversations",
      enabled: true,
      notify_to: "all_staff",
    });
    setShowForm(true);
  };

  const handleEdit = (rule: TConversationAlertRule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      trigger: rule.trigger,
      extractions: rule.extractions || {},
      scope: rule.scope,
      enabled: rule.enabled,
      notify_to: rule.notify_to,
    });
    setShowForm(true);
  };

  const handleDelete = async (ruleId: string) => {
    if (!window.confirm(t("confirm-delete-alert-rule") || "Are you sure you want to delete this alert rule?")) {
      return;
    }
    try {
      await deleteAlertRule(ruleId);
      loadAlertRules();
    } catch (error) {
      console.error("Error deleting alert rule:", error);
      alert(t("error-deleting-alert-rule") || "Error deleting alert rule");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingRule) {
        await updateAlertRule(editingRule.id, formData);
      } else {
        await createAlertRule(formData);
      }
      setShowForm(false);
      setEditingRule(null);
      loadAlertRules();
    } catch (error: any) {
      console.error("Error saving alert rule:", error);
      alert(error.response?.data?.message || t("error-saving-alert-rule") || "Error saving alert rule");
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingRule(null);
    setFormData({
      name: "",
      trigger: "",
      extractions: {},
      scope: "all_conversations",
      enabled: true,
      notify_to: "all_staff",
    });
  };

  return (
    <ProtectedRoute featureFlag="alert-rules-manager">
      <main className="d-flex pos-relative h-viewport">
        {chatState.isSidebarOpened && <Sidebar />}
        <div className="dashboard-container">
          <div className="dashboard-header">
            <button 
              className="dashboard-back-button"
              onClick={() => navigate("/dashboard")}
            >
              ← {t("back-to-dashboard")}
            </button>
            <h1>{t("alert-rules") || "Alert Rules"}</h1>
          </div>

          <div className="alert-rules-actions">
            <button 
              className="dashboard-button primary"
              onClick={handleCreate}
            >
              {t("create-alert-rule") || "+ Create Alert Rule"}
            </button>
          </div>

          {isLoading ? (
            <div className="dashboard-loading">{t("loading")}...</div>
          ) : alertRules.length === 0 ? (
            <div className="alert-rules-empty">
              {t("no-alert-rules-found") || "No alert rules found. Create your first one!"}
            </div>
          ) : (
            <div className="alert-rules-list">
              {alertRules.map((rule) => (
                <AlertRuleCard
                  key={rule.id}
                  rule={rule}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                  t={t}
                />
              ))}
            </div>
          )}

          {showForm && (
            <AlertRuleForm
              formData={formData}
              setFormData={setFormData}
              onSubmit={handleSubmit}
              onCancel={handleCancel}
              editingRule={editingRule}
              t={t}
            />
          )}
        </div>
      </main>
    </ProtectedRoute>
  );
}

interface AlertRuleCardProps {
  rule: TConversationAlertRule;
  onEdit: (rule: TConversationAlertRule) => void;
  onDelete: (ruleId: string) => void;
  t: any;
}

function AlertRuleCard({ rule, onEdit, onDelete, t }: AlertRuleCardProps) {
  return (
    <div className={`alert-rule-card ${rule.enabled ? "enabled" : "disabled"}`}>
      <div className="alert-rule-header">
        <h3>{rule.name}</h3>
        <div className="alert-rule-status">
          <span className={`status-badge ${rule.enabled ? "active" : "inactive"}`}>
            {rule.enabled ? t("enabled") || "Enabled" : t("disabled") || "Disabled"}
          </span>
        </div>
      </div>
      <div className="alert-rule-body">
        <p className="alert-rule-trigger">{rule.trigger}</p>
        <div className="alert-rule-meta">
          <span>{t("scope") || "Scope"}: {rule.scope === "all_conversations" ? t("all-conversations") || "All Conversations" : t("selected-agents") || "Selected Agents"}</span>
          <span>{t("notify-to") || "Notify To"}: {rule.notify_to === "all_staff" ? t("all-staff") || "All Staff" : t("selected-members") || "Selected Members"}</span>
        </div>
      </div>
      <div className="alert-rule-actions">
        <button 
          className="alert-rule-button edit"
          onClick={() => onEdit(rule)}
        >
          {t("edit") || "Edit"}
        </button>
        <button 
          className="alert-rule-button delete"
          onClick={() => onDelete(rule.id)}
        >
          {t("delete") || "Delete"}
        </button>
      </div>
    </div>
  );
}

interface AlertRuleFormProps {
  formData: {
    name: string;
    trigger: string;
    extractions: Record<string, any>;
    scope: "all_conversations" | "selected_agents";
    enabled: boolean;
    notify_to: "all_staff" | "selected_members";
  };
  setFormData: React.Dispatch<React.SetStateAction<any>>;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
  editingRule: TConversationAlertRule | null;
  t: any;
}

function AlertRuleForm({ formData, setFormData, onSubmit, onCancel, editingRule, t }: AlertRuleFormProps) {
  return (
    <div className="alert-rule-form-overlay">
      <div className="alert-rule-form">
        <h2>{editingRule ? t("edit-alert-rule") || "Edit Alert Rule" : t("create-alert-rule") || "Create Alert Rule"}</h2>
        <form onSubmit={onSubmit}>
          <div className="form-group">
            <label>{t("name") || "Name"}</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label>{t("trigger") || "Trigger Description"}</label>
            <textarea
              value={formData.trigger}
              onChange={(e) => setFormData({ ...formData, trigger: e.target.value })}
              required
              rows={4}
              placeholder={t("trigger-description-placeholder") || "Describe when this alert should be triggered..."}
            />
          </div>

          <div className="form-group">
            <label>{t("scope") || "Scope"}</label>
            <select
              value={formData.scope}
              onChange={(e) => setFormData({ ...formData, scope: e.target.value as "all_conversations" | "selected_agents" })}
            >
              <option value="all_conversations">{t("all-conversations") || "All Conversations"}</option>
              <option value="selected_agents">{t("selected-agents") || "Selected Agents"}</option>
            </select>
          </div>

          <div className="form-group">
            <label>{t("notify-to") || "Notify To"}</label>
            <select
              value={formData.notify_to}
              onChange={(e) => setFormData({ ...formData, notify_to: e.target.value as "all_staff" | "selected_members" })}
            >
              <option value="all_staff">{t("all-staff") || "All Staff"}</option>
              <option value="selected_members">{t("selected-members") || "Selected Members"}</option>
            </select>
          </div>

          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
              />
              {t("enabled") || "Enabled"}
            </label>
          </div>

          <div className="form-actions">
            <button type="button" className="button secondary" onClick={onCancel}>
              {t("cancel") || "Cancel"}
            </button>
            <button type="submit" className="button primary">
              {editingRule ? t("update") || "Update" : t("create") || "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
