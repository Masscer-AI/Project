import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { getAlerts, updateAlertStatus } from "../../modules/apiCalls";
import { TConversationAlert } from "../../types";
import { ProtectedRoute } from "../../components/ProtectedRoute/ProtectedRoute";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import "./AlertsPage.css";

export default function AlertsPage() {
  const { chatState, startup, toggleSidebar } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
    toggleSidebar: state.toggleSidebar,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<TConversationAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "notified" | "resolved" | "dismissed">("all");
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  useEffect(() => {
    startup();
  }, []);
  
  useEffect(() => {
    loadAlerts();
  }, [statusFilter]);
  

  const loadAlerts = async () => {
    try {
      setIsLoading(true);
      const data = await getAlerts(statusFilter);
      setAlerts(data);
    } catch (error) {
      console.error("Error loading alerts:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStatusChange = async (alertId: string, newStatus: "RESOLVED" | "DISMISSED") => {
    try {
      await updateAlertStatus(alertId, newStatus);
      loadAlerts(); // Reload alerts after update
    } catch (error) {
      console.error("Error updating alert status:", error);
    }
  };

  const handleViewConversation = (conversationId: string) => {
    navigate(`/chat?conversation=${conversationId}`);
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
                  className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                    hoveredButton === 'back' 
                      ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                      : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                  }`}
                  style={{ transform: 'none' }}
                  onMouseEnter={() => setHoveredButton('back')}
                  onMouseLeave={() => setHoveredButton(null)}
                  onClick={() => navigate("/dashboard")}
                >
                  ← {t("back-to-dashboard")}
                </button>
              </div>
              <h1 className="text-4xl font-bold mb-8 text-center text-white tracking-tight" style={{ textShadow: '0 2px 8px rgba(110, 91, 255, 0.2)' }}>
                {t("alerts")}
              </h1>
            </div>

            {/* Filtros */}
            <div className="flex justify-center gap-3 mb-8 flex-wrap">
              <button
                className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                  statusFilter === "all" 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onClick={() => setStatusFilter("all")}
              >
                {t("all")}
              </button>
              <button
                className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                  statusFilter === "pending" 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onClick={() => setStatusFilter("pending")}
              >
                {t("pending")}
              </button>
              <button
                className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                  statusFilter === "notified" 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onClick={() => setStatusFilter("notified")}
              >
                {t("notified")}
              </button>
              <button
                className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                  statusFilter === "resolved" 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onClick={() => setStatusFilter("resolved")}
              >
                {t("resolved")}
              </button>
              <button
                className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                  statusFilter === "dismissed" 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onClick={() => setStatusFilter("dismissed")}
              >
                {t("dismissed")}
              </button>
            </div>

            {isLoading ? (
              <div className="text-center py-10 text-lg text-[rgb(156,156,156)]">
                {t("loading")}...
              </div>
            ) : alerts.length === 0 ? (
              <div className="text-center py-16 text-xl text-[rgb(156,156,156)]">
                {t("no-alerts-found")}
              </div>
            ) : (
              <div className="flex justify-center w-full">
                <div className="grid grid-cols-1 gap-6 w-full max-w-4xl">
                  {alerts.map((alert) => (
                    <AlertCard
                      key={alert.id}
                      alert={alert}
                      onStatusChange={handleStatusChange}
                      onViewConversation={handleViewConversation}
                      t={t}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
  );
}

interface AlertCardProps {
  alert: TConversationAlert;
  onStatusChange: (alertId: string, status: "RESOLVED" | "DISMISSED") => void;
  onViewConversation: (conversationId: string) => void;
  t: any;
}

function AlertCard({ alert, onStatusChange, onViewConversation, t }: AlertCardProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "PENDING":
        return "status-pending";
      case "NOTIFIED":
        return "status-notified";
      case "RESOLVED":
        return "status-resolved";
      case "DISMISSED":
        return "status-dismissed";
      default:
        return "";
    }
  };

  const getStatusBadgeStyle = (status: string) => {
    switch (status) {
      case "PENDING":
        return 'bg-orange-500/20 text-orange-400 border border-orange-500/30';
      case "NOTIFIED":
        return 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
      case "RESOLVED":
        return 'bg-green-500/20 text-green-400 border border-green-500/30';
      case "DISMISSED":
        return 'bg-gray-500/20 text-gray-400 border border-gray-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border border-gray-500/30';
    }
  };

  return (
    <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 flex flex-col gap-4 shadow-lg">
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-3 flex-wrap">
          <h3 className="text-xl font-bold text-white">{alert.title}</h3>
          <span className={`px-4 py-2 rounded-full text-xs font-semibold whitespace-nowrap ${getStatusBadgeStyle(alert.status)}`}>
            {t(alert.status.toLowerCase())}
          </span>
        </div>
        <span className="text-sm text-[rgb(156,156,156)]">
          {new Date(alert.created_at).toLocaleDateString()} {new Date(alert.created_at).toLocaleTimeString()}
        </span>
      </div>

      <div className="flex flex-col gap-2 text-sm text-[rgb(156,156,156)]">
        <div>
          <strong className="text-white">{t("rule")}:</strong> {alert.alert_rule.name}
        </div>
        <div>
          <strong className="text-white">{t("conversation")}:</strong>{" "}
          <button
            className="text-blue-400 hover:text-blue-300 underline cursor-pointer"
            onClick={() => onViewConversation(alert.conversation_id)}
          >
            {alert.conversation_title || alert.conversation_id.slice(0, 8)}
          </button>
        </div>
      </div>

      <button
        className="px-6 py-2 rounded-full font-normal text-sm cursor-pointer border bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)] w-fit"
        style={{ transform: 'none' }}
        onClick={() => setShowDetails(!showDetails)}
      >
        {showDetails ? t("hide-details") : t("show-details")}
      </button>

      {showDetails && (
        <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.1)] space-y-4">
          <div>
            <h4 className="text-sm font-medium text-[rgb(156,156,156)] mb-2">{t("ai-analysis")}</h4>
            <p className="text-sm leading-relaxed text-[rgb(156,156,156)] whitespace-pre-wrap">{alert.reasoning}</p>
          </div>

          {Object.keys(alert.extractions).length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-[rgb(156,156,156)] mb-2">{t("extracted-data")}</h4>
              <div className="flex flex-col gap-2">
                {Object.entries(alert.extractions).map(([key, value]) => (
                  <div key={key} className="px-4 py-2 bg-[rgba(35,33,39,0.5)] rounded-lg text-sm">
                    <strong className="text-blue-400">{key}:</strong>{" "}
                    <span className="text-[rgb(156,156,156)]">
                      {typeof value === "object" ? JSON.stringify(value) : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {alert.resolved_by_username && (
            <div className="text-sm text-[rgb(156,156,156)]">
              <strong className="text-white">{t("resolved-by")}:</strong> {alert.resolved_by_username}
            </div>
          )}

          {alert.dismissed_by_username && (
            <div className="text-sm text-[rgb(156,156,156)]">
              <strong className="text-white">{t("dismissed-by")}:</strong> {alert.dismissed_by_username}
            </div>
          )}
        </div>
      )}

      {alert.status === "PENDING" || alert.status === "NOTIFIED" ? (
        <div className="flex gap-3 mt-2 pt-4 border-t border-[rgba(255,255,255,0.1)]">
          <button
            className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
              hoveredButton === 'resolve' 
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('resolve')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={() => onStatusChange(alert.id, "RESOLVED")}
          >
            {t("resolve")}
          </button>
          <button
            className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
              hoveredButton === 'dismiss' 
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('dismiss')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={() => onStatusChange(alert.id, "DISMISSED")}
          >
            {t("dismiss")}
          </button>
        </div>
      ) : null}
    </div>
  );
}

