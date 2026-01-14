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
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

export default function AlertRulesPage() {
  const { chatState, startup, toggleSidebar } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
    toggleSidebar: state.toggleSidebar,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [alertRules, setAlertRules] = useState<TConversationAlertRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<TConversationAlertRule | null>(null);
  const [hoveredHeaderButton, setHoveredHeaderButton] = useState<string | null>(null);
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
  }, [startup]);

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
      <main className="d-flex pos-relative h-viewport">
        {chatState.isSidebarOpened && <Sidebar />}
        <div className="dashboard-container relative">
          {!chatState.isSidebarOpened && (
            <div className="absolute top-6 left-6 z-10">
              <SvgButton
                extraClass="pressable active-on-hover"
                onClick={toggleSidebar}
                svg={SVGS.burger}
              />
            </div>
          )}
          <div className="max-w-7xl mx-auto px-4">
            <div className="dashboard-header mb-8">
              <div className="flex items-center gap-4 mb-4">
                {!chatState.isSidebarOpened && (
                  <div className="w-10"></div>
                )}
                <button 
                  className={`px-3 md:px-6 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                    hoveredHeaderButton === 'back' 
                      ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                      : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                  }`}
                  style={{ transform: 'none' }}
                  onMouseEnter={() => setHoveredHeaderButton('back')}
                  onMouseLeave={() => setHoveredHeaderButton(null)}
                  onClick={() => {
                    setHoveredHeaderButton('back');
                    setTimeout(() => {
                      navigate("/dashboard");
                      setHoveredHeaderButton(null);
                    }, 200);
                  }}
                >
                  <span className="md:mr-1">←</span>
                  <span className="hidden md:inline">{t("back-to-dashboard")}</span>
                </button>
              </div>
              <h1 className="text-2xl md:text-4xl font-bold mb-4 md:mb-8 text-center text-white tracking-tight" style={{ textShadow: '0 2px 8px rgba(110, 91, 255, 0.2)' }}>
                {t("alert-rules") || "Alert Rules"}
              </h1>
            </div>

            <div className="mb-8 md:mb-12 text-center">
              <button 
                className={`px-3 py-1.5 md:px-4 md:py-3 rounded-full font-normal text-xs md:text-sm cursor-pointer border ${
                  hoveredHeaderButton === 'create' 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onMouseEnter={() => setHoveredHeaderButton('create')}
                onMouseLeave={() => setHoveredHeaderButton(null)}
                onClick={() => {
                  setHoveredHeaderButton('create');
                  setTimeout(() => {
                    handleCreate();
                    setHoveredHeaderButton(null);
                  }, 200);
                }}
              >
                {t("create-alert-rule") || "+ Nueva regla"}
              </button>
            </div>

            {isLoading ? (
              <div className="text-center py-10 text-lg text-[rgb(156,156,156)]">
                {t("loading")}...
              </div>
            ) : alertRules.length === 0 ? (
              <div className="text-center py-16 text-xl text-[rgb(156,156,156)]">
                {t("no-alert-rules-found") || "No alert rules found. Create your first one!"}
              </div>
            ) : (
              <div className="flex justify-center w-full">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-6 w-full max-w-fit">
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
              </div>
            )}
          </div>

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
  );
}

interface AlertRuleCardProps {
  rule: TConversationAlertRule;
  onEdit: (rule: TConversationAlertRule) => void;
  onDelete: (ruleId: string) => void;
  t: any;
}

function AlertRuleCard({ rule, onEdit, onDelete, t }: AlertRuleCardProps) {
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  
  return (
    <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-xl md:rounded-2xl p-4 md:p-6 flex flex-col gap-2 md:gap-4 shadow-lg">
      <div className="flex justify-between items-start flex-col md:flex-row gap-2 md:gap-0">
        <h3 className="text-base md:text-xl font-bold text-white md:ml-2">{rule.name}</h3>
        <span className={`px-2 py-1 md:px-4 md:py-2 rounded-full text-[10px] md:text-xs font-semibold whitespace-nowrap ${
          rule.enabled 
            ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
            : 'bg-red-500/20 text-red-400 border border-red-500/30'
        }`}>
          {rule.enabled ? t("enabled") || "Enabled" : t("disabled") || "Disabled"}
        </span>
      </div>
      
      <p className="text-xs md:text-sm leading-relaxed text-[rgb(156,156,156)]">
        {rule.trigger}
      </p>
      
      <div className="flex flex-col gap-1.5 md:gap-2 text-xs md:text-sm text-[rgb(156,156,156)]">
        <span>
          {t("scope") || "Scope"}: {rule.scope === "all_conversations" ? t("all-conversations") || "All Conversations" : t("selected-agents") || "Selected Agents"}
        </span>
        <span>
          {t("notify-to") || "Notify To"}: {rule.notify_to === "all_staff" ? t("all-staff") || "All Staff" : t("selected-members") || "Selected Members"}
        </span>
      </div>
      
      <div className="flex gap-2 md:gap-3 mt-1 md:mt-2 pt-2 md:pt-4 border-t border-[rgba(255,255,255,0.1)]">
        <button 
          className={`px-3 py-1.5 md:px-6 md:py-2 rounded-full font-normal text-xs md:text-sm cursor-pointer border ${
            hoveredButton === 'edit' 
              ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
              : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
          }`}
          style={{ transform: 'none' }}
          onMouseEnter={() => setHoveredButton('edit')}
          onMouseLeave={() => setHoveredButton(null)}
          onClick={() => {
            setHoveredButton('edit');
            setTimeout(() => {
              onEdit(rule);
              setHoveredButton(null);
            }, 200);
          }}
        >
          {t("edit") || "Edit"}
        </button>
        <button 
          className={`px-3 py-1.5 md:px-6 md:py-2 rounded-full font-normal text-xs md:text-sm cursor-pointer border ${
            hoveredButton === 'delete' 
              ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
              : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
          }`}
          style={{ transform: 'none' }}
          onMouseEnter={() => setHoveredButton('delete')}
          onMouseLeave={() => setHoveredButton(null)}
          onClick={() => {
            setHoveredButton('delete');
            setTimeout(() => {
              onDelete(rule.id);
              setHoveredButton(null);
            }, 200);
          }}
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
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  
  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-2 md:p-4">
      <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-xl md:rounded-2xl p-4 md:p-8 max-w-2xl w-full max-h-[95vh] md:max-h-[90vh] overflow-y-auto shadow-lg overflow-x-hidden">
        <h2 className="text-base md:text-2xl font-bold text-white text-center mb-3 md:mb-6" style={{ textShadow: '0 2px 8px rgba(110, 91, 255, 0.2)' }}>
          {editingRule ? t("edit-alert-rule") : t("create-alert-rule")}
        </h2>
        <form onSubmit={onSubmit} className="space-y-3 md:space-y-6">
          <div className="space-y-1.5 md:space-y-2">
            <label className="block text-xs md:text-sm font-medium text-[rgb(156,156,156)]">{t("name")}</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              className="w-full !px-3 !py-2 md:!px-4 md:!py-3 bg-[rgba(35,33,39,0.5)] border border-[rgba(156,156,156,0.3)] rounded-lg text-xs md:text-sm text-white focus:outline-none focus:border-[rgba(156,156,156,0.5)] transition-colors"
            />
          </div>

          <div className="space-y-1.5 md:space-y-2">
            <label className="block text-xs md:text-sm font-medium text-[rgb(156,156,156)]">{t("trigger")}</label>
            <textarea
              value={formData.trigger}
              onChange={(e) => setFormData({ ...formData, trigger: e.target.value })}
              required
              rows={4}
              placeholder={t("trigger-description-placeholder")}
              className="w-full !px-3 !py-2 md:!px-4 md:!py-3 bg-[rgba(35,33,39,0.5)] border border-[rgba(156,156,156,0.3)] rounded-lg text-xs md:text-sm text-white focus:outline-none focus:border-[rgba(156,156,156,0.5)] transition-colors resize-vertical"
            />
          </div>

          <div className="space-y-1.5 md:space-y-2">
            <label className="block text-xs md:text-sm font-medium text-[rgb(156,156,156)]">{t("scope")}</label>
            <select
              value={formData.scope}
              onChange={(e) => setFormData({ ...formData, scope: e.target.value as "all_conversations" | "selected_agents" })}
              className="w-full px-2 py-1.5 md:px-4 md:py-2.5 bg-[rgba(35,33,39,0.5)] border border-[rgba(156,156,156,0.3)] rounded-lg text-xs md:text-sm text-white focus:outline-none focus:border-[rgba(156,156,156,0.5)] transition-colors appearance-none max-w-full box-border"
            >
              <option value="all_conversations" className="text-xs md:text-sm">{t("all-conversations")}</option>
              <option value="selected_agents" className="text-xs md:text-sm">{t("selected-agents")}</option>
            </select>
          </div>

          <div className="space-y-1.5 md:space-y-2">
            <label className="block text-xs md:text-sm font-medium text-[rgb(156,156,156)]">{t("notify-to")}</label>
            <select
              value={formData.notify_to}
              onChange={(e) => setFormData({ ...formData, notify_to: e.target.value as "all_staff" | "selected_members" })}
              className="w-full px-2 py-1.5 md:px-4 md:py-2.5 bg-[rgba(35,33,39,0.5)] border border-[rgba(156,156,156,0.3)] rounded-lg text-xs md:text-sm text-white focus:outline-none focus:border-[rgba(156,156,156,0.5)] transition-colors appearance-none max-w-full box-border"
            >
              <option value="all_staff" className="text-xs md:text-sm">{t("all-staff")}</option>
              <option value="selected_members" className="text-xs md:text-sm">{t("selected-members")}</option>
            </select>
          </div>

          <div className="space-y-1.5 md:space-y-2">
            <label className="flex items-center text-xs md:text-sm font-medium text-[rgb(156,156,156)] cursor-pointer">
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                className="mr-2 w-4 h-4 cursor-pointer"
              />
              {t("enabled")}
            </label>
          </div>

          <div className="flex justify-end gap-2 md:gap-4 pt-3 md:pt-6 border-t border-[rgba(255,255,255,0.1)]">
            <button 
              type="button" 
              className={`px-3 py-1.5 md:px-6 md:py-2 rounded-full font-normal text-xs md:text-sm cursor-pointer border ${
                hoveredButton === 'cancel' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredButton('cancel')}
              onMouseLeave={() => setHoveredButton(null)}
              onClick={onCancel}
            >
              {t("cancel")}
            </button>
            <button 
              type="submit" 
              className={`px-3 py-1.5 md:px-6 md:py-2 rounded-full font-normal text-xs md:text-sm cursor-pointer border ${
                hoveredButton === 'submit' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredButton('submit')}
              onMouseLeave={() => setHoveredButton(null)}
            >
              {editingRule ? t("update") : t("create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
