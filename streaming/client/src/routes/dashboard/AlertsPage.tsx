import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { getAlerts, updateAlertStatus } from "../../modules/apiCalls";
import { TConversationAlert } from "../../types";
import { ProtectedRoute } from "../../components/ProtectedRoute/ProtectedRoute";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import "./AlertsPage.css";

export default function AlertsPage() {
  const { chatState, startup } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<TConversationAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "notified" | "resolved" | "dismissed">("all");

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
    <ProtectedRoute featureFlag="conversations-dashboard">
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
            <h1>{t("alerts")}</h1>
          </div>

          {/* Filtros */}
          <div className="alerts-filters">
            <button
              className={`alert-filter-button ${statusFilter === "all" ? "active" : ""}`}
              onClick={() => setStatusFilter("all")}
            >
              {t("all")}
            </button>
            <button
              className={`alert-filter-button ${statusFilter === "pending" ? "active" : ""}`}
              onClick={() => setStatusFilter("pending")}
            >
              {t("pending")}
            </button>
            <button
              className={`alert-filter-button ${statusFilter === "notified" ? "active" : ""}`}
              onClick={() => setStatusFilter("notified")}
            >
              {t("notified")}
            </button>
            <button
              className={`alert-filter-button ${statusFilter === "resolved" ? "active" : ""}`}
              onClick={() => setStatusFilter("resolved")}
            >
              {t("resolved")}
            </button>
            <button
              className={`alert-filter-button ${statusFilter === "dismissed" ? "active" : ""}`}
              onClick={() => setStatusFilter("dismissed")}
            >
              {t("dismissed")}
            </button>
          </div>

          {isLoading ? (
            <div className="dashboard-loading">{t("loading")}...</div>
          ) : alerts.length === 0 ? (
            <div className="alerts-empty">
              {t("no-alerts-found")}
            </div>
          ) : (
            <div className="alerts-list">
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
          )}
        </div>
      </main>
    </ProtectedRoute>
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

  return (
    <div className={`alert-card ${getStatusColor(alert.status)}`}>
      <div className="alert-card-header">
        <div className="alert-card-title-section">
          <h3 className="alert-card-title">{alert.title}</h3>
          <span className={`alert-status-badge ${getStatusColor(alert.status)}`}>
            {t(alert.status.toLowerCase())}
          </span>
        </div>
        <div className="alert-card-meta">
          <span className="alert-date">
            {new Date(alert.created_at).toLocaleDateString()} {new Date(alert.created_at).toLocaleTimeString()}
          </span>
        </div>
      </div>

      <div className="alert-card-body">
        <div className="alert-card-info">
          <div className="alert-info-item">
            <strong>{t("rule")}:</strong> {alert.alert_rule.name}
          </div>
          <div className="alert-info-item">
            <strong>{t("conversation")}:</strong>{" "}
            <button
              className="alert-link-button"
              onClick={() => onViewConversation(alert.conversation_id)}
            >
              {alert.conversation_title || alert.conversation_id.slice(0, 8)}
            </button>
          </div>
        </div>

        <button
          className="alert-toggle-details"
          onClick={() => setShowDetails(!showDetails)}
        >
          {showDetails ? t("hide-details") : t("show-details")}
        </button>

        {showDetails && (
          <div className="alert-details">
            <div className="alert-detail-section">
              <h4>{t("ai-analysis")}</h4>
              <p className="alert-reasoning">{alert.reasoning}</p>
            </div>

            {Object.keys(alert.extractions).length > 0 && (
              <div className="alert-detail-section">
                <h4>{t("extracted-data")}</h4>
                <div className="alert-extractions">
                  {Object.entries(alert.extractions).map(([key, value]) => (
                    <div key={key} className="alert-extraction-item">
                      <strong>{key}:</strong>{" "}
                      <span>
                        {typeof value === "object" ? JSON.stringify(value) : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {alert.resolved_by_username && (
              <div className="alert-detail-section">
                <strong>{t("resolved-by")}:</strong> {alert.resolved_by_username}
              </div>
            )}

            {alert.dismissed_by_username && (
              <div className="alert-detail-section">
                <strong>{t("dismissed-by")}:</strong> {alert.dismissed_by_username}
              </div>
            )}
          </div>
        )}
      </div>

      {alert.status === "PENDING" || alert.status === "NOTIFIED" ? (
        <div className="alert-card-actions">
          <button
            className="alert-action-button resolve"
            onClick={() => onStatusChange(alert.id, "RESOLVED")}
          >
            {t("resolve")}
          </button>
          <button
            className="alert-action-button dismiss"
            onClick={() => onStatusChange(alert.id, "DISMISSED")}
          >
            {t("dismiss")}
          </button>
        </div>
      ) : null}
    </div>
  );
}

