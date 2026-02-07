import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import {
  getChatWidgets,
  createChatWidget,
  updateChatWidget,
  deleteChatWidget,
} from "../../modules/apiCalls";
import { TChatWidget } from "../../types";
import toast from "react-hot-toast";
import { SvgButton } from "../SvgButton/SvgButton";
import { Icon } from "../Icon/Icon";

interface WidgetManagerProps {
  hide: () => void;
}

export const WidgetManager: React.FC<WidgetManagerProps> = ({ hide }) => {
  const { t } = useTranslation();
  const { agents } = useStore((s) => ({ agents: s.agents }));

  const [widgets, setWidgets] = useState<TChatWidget[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingWidget, setEditingWidget] = useState<TChatWidget | null>(null);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    agent_id: null as number | null,
    enabled: true,
    web_search_enabled: false,
    rag_enabled: false,
  });

  useEffect(() => {
    loadWidgets();
  }, []);

  const loadWidgets = async () => {
    try {
      setIsLoading(true);
      const data = await getChatWidgets();
      setWidgets(data);
    } catch (error) {
      console.error("Error loading widgets:", error);
      toast.error(t("error-loading-widgets"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.name.trim()) {
      toast.error(t("widget-name-required"));
      return;
    }

    try {
      const newWidget = await createChatWidget({
        name: formData.name,
        agent_id: formData.agent_id,
        enabled: formData.enabled,
        web_search_enabled: formData.web_search_enabled,
        rag_enabled: formData.rag_enabled,
      });
      setWidgets([newWidget, ...widgets]);
      setShowCreateForm(false);
      resetForm();
      toast.success(t("widget-created"));
    } catch (error) {
      console.error("Error creating widget:", error);
      toast.error(t("error-creating-widget"));
    }
  };

  const handleUpdate = async () => {
    if (!editingWidget) return;
    if (!formData.name.trim()) {
      toast.error(t("widget-name-required"));
      return;
    }

    try {
      const updatedWidget = await updateChatWidget(editingWidget.id, {
        name: formData.name,
        agent_id: formData.agent_id,
        enabled: formData.enabled,
        web_search_enabled: formData.web_search_enabled,
        rag_enabled: formData.rag_enabled,
      });
      setWidgets(widgets.map((w) => (w.id === updatedWidget.id ? updatedWidget : w)));
      setEditingWidget(null);
      resetForm();
      toast.success(t("widget-updated"));
    } catch (error) {
      console.error("Error updating widget:", error);
      toast.error(t("error-updating-widget"));
    }
  };

  const handleDelete = async (widgetId: number) => {
    try {
      await deleteChatWidget(widgetId);
      setWidgets(widgets.filter((w) => w.id !== widgetId));
      toast.success(t("widget-deleted"));
    } catch (error) {
      console.error("Error deleting widget:", error);
      toast.error(t("error-deleting-widget"));
    }
  };

  const copyEmbedCode = (embedCode: string) => {
    navigator.clipboard.writeText(embedCode);
    toast.success(t("copied-to-clipboard"));
  };

  const resetForm = () => {
    setFormData({
      name: "",
      agent_id: null,
      enabled: true,
      web_search_enabled: false,
      rag_enabled: false,
    });
  };

  const startEdit = (widget: TChatWidget) => {
    setEditingWidget(widget);
    const agent = agents.find((a) => a.slug === widget.agent_slug);
    setFormData({
      name: widget.name,
      agent_id: agent?.id || null,
      enabled: widget.enabled,
      web_search_enabled: widget.web_search_enabled,
      rag_enabled: widget.rag_enabled,
    });
  };

  const cancelEdit = () => {
    setEditingWidget(null);
    setShowCreateForm(false);
    resetForm();
  };

  const renderForm = () => (
    <div className="flex flex-col gap-4 p-4 bg-[rgba(255,255,255,0.05)] rounded-xl border border-[rgba(255,255,255,0.1)]">
      <h3 className="text-white font-semibold">
        {editingWidget ? t("edit-widget") : t("create-widget")}
      </h3>

      <div className="flex flex-col gap-2">
        <label className="text-[rgb(156,156,156)] text-sm">{t("name")}</label>
        <input
          type="text"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder={t("widget-name-placeholder")}
          className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-[rgb(156,156,156)] text-sm">{t("agent")}</label>
        <select
          value={formData.agent_id || ""}
          onChange={(e) =>
            setFormData({
              ...formData,
              agent_id: e.target.value ? parseInt(e.target.value) : null,
            })
          }
          className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
        >
          <option value="">{t("select-agent")}</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-white cursor-pointer">
          <input
            type="checkbox"
            checked={formData.enabled}
            onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
            className="w-4 h-4"
          />
          {t("enabled")}
        </label>

        <label className="flex items-center gap-2 text-white cursor-pointer">
          <input
            type="checkbox"
            checked={formData.web_search_enabled}
            onChange={(e) =>
              setFormData({ ...formData, web_search_enabled: e.target.checked })
            }
            className="w-4 h-4"
          />
          {t("web-search")}
        </label>

        <label className="flex items-center gap-2 text-white cursor-pointer">
          <input
            type="checkbox"
            checked={formData.rag_enabled}
            onChange={(e) =>
              setFormData({ ...formData, rag_enabled: e.target.checked })
            }
            className="w-4 h-4"
          />
          {t("rag")}
        </label>
      </div>

      <div className="flex gap-2">
        <button
          onClick={editingWidget ? handleUpdate : handleCreate}
          className={`flex-1 px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
            hoveredButton === "save"
              ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
              : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
          }`}
          onMouseEnter={() => setHoveredButton("save")}
          onMouseLeave={() => setHoveredButton(null)}
        >
          {editingWidget ? t("update") : t("create")}
        </button>
        <button
          onClick={cancelEdit}
          className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
            hoveredButton === "cancel"
              ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
              : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
          }`}
          onMouseEnter={() => setHoveredButton("cancel")}
          onMouseLeave={() => setHoveredButton(null)}
        >
          {t("cancel")}
        </button>
      </div>
    </div>
  );

  const renderWidgetCard = (widget: TChatWidget) => (
    <div
      key={widget.id}
      className="flex flex-col gap-3 p-4 bg-[rgba(255,255,255,0.05)] rounded-xl border border-[rgba(255,255,255,0.1)]"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h4 className="text-white font-semibold">{widget.name}</h4>
          <span
            className={`px-2 py-0.5 rounded-full text-xs ${
              widget.enabled
                ? "bg-green-500/20 text-green-400"
                : "bg-red-500/20 text-red-400"
            }`}
          >
            {widget.enabled ? t("enabled") : t("disabled")}
          </span>
        </div>
        <div className="flex gap-2">
          <SvgButton
            svg={<Icon name="Pencil" size={20} />}
            onClick={() => startEdit(widget)}
            title={t("edit")}
            extraClass="hover:!bg-white hover:!border-white [&>svg]:hover:!fill-black"
          />
          <SvgButton
            svg={<Icon name="Trash2" size={20} />}
            onClick={() => handleDelete(widget.id)}
            title={t("delete")}
            extraClass="hover:!bg-red-500 hover:!border-red-500"
          />
        </div>
      </div>

      {widget.agent_name && (
        <div className="text-[rgb(156,156,156)] text-sm">
          {t("agent")}: <span className="text-white">{widget.agent_name}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {widget.web_search_enabled && (
          <span className="px-2 py-0.5 rounded-full text-xs bg-blue-500/20 text-blue-400">
            {t("web-search")}
          </span>
        )}
        {widget.rag_enabled && (
          <span className="px-2 py-0.5 rounded-full text-xs bg-purple-500/20 text-purple-400">
            {t("rag")}
          </span>
        )}
      </div>

      <div className="mt-2">
        <label className="text-[rgb(156,156,156)] text-sm block mb-1">
          {t("embed-code")}
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={widget.embed_code}
            readOnly
            className="flex-1 p-2 bg-[rgba(0,0,0,0.3)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white text-sm font-mono"
          />
          <button
            onClick={() => copyEmbedCode(widget.embed_code)}
            className={`px-4 py-2 rounded-lg font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
              hoveredButton === `copy-${widget.id}`
                ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
            }`}
            onMouseEnter={() => setHoveredButton(`copy-${widget.id}`)}
            onMouseLeave={() => setHoveredButton(null)}
          >
            <Icon name="Copy" size={16} />
            {t("copy")}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <Modal hide={hide} minHeight="fit-content">
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-white">{t("chat-widgets")}</h2>
          {!showCreateForm && !editingWidget && (
            <button
              onClick={() => setShowCreateForm(true)}
              className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                hoveredButton === "new-widget"
                  ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                  : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
              }`}
              onMouseEnter={() => setHoveredButton("new-widget")}
              onMouseLeave={() => setHoveredButton(null)}
            >
              <Icon name="Plus" size={20} />
              {t("new-widget")}
            </button>
          )}
        </div>

        <p className="text-[rgb(156,156,156)]">{t("widget-manager-description")}</p>

        {(showCreateForm || editingWidget) && renderForm()}

        {isLoading ? (
          <div className="text-center py-10 text-[rgb(156,156,156)]">
            {t("loading")}...
          </div>
        ) : widgets.length === 0 ? (
          <div className="text-center py-10 text-[rgb(156,156,156)]">
            {t("no-widgets-found")}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {widgets.map(renderWidgetCard)}
          </div>
        )}
      </div>
    </Modal>
  );
};
