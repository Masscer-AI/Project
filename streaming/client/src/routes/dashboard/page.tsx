import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { getAllConversations, getAlertStats } from "../../modules/apiCalls";
import { TConversation, TAlertStats } from "../../types";
import { ProtectedRoute } from "../../components/ProtectedRoute/ProtectedRoute";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { ConversationsTable } from "./ConversationsTable";
import "./page.css";

export default function DashboardPage() {
  const { chatState, startup } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<TConversation[]>([]);
  const [alertStats, setAlertStats] = useState<TAlertStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showTable, setShowTable] = useState(false);
  const canManageAlertRules = useIsFeatureEnabled("alert-rules-manager");

  useEffect(() => {
    startup();
    loadConversations();
    loadAlertStats();
  }, []);

  const loadConversations = async () => {
    try {
      const data = await getAllConversations();
      setConversations(data);
    } catch (error) {
      console.error("Error loading conversations:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadAlertStats = async () => {
    try {
      const stats = await getAlertStats();
      setAlertStats(stats);
    } catch (error) {
      console.error("Error loading alert stats:", error);
    }
  };

  return (
    <ProtectedRoute featureFlag="conversations-dashboard">
      <main className="d-flex pos-relative h-viewport">
        {chatState.isSidebarOpened && <Sidebar />}
        <div className="dashboard-container">
          <div className="dashboard-header">
            <h1>{t("conversations-dashboard")}</h1>
          </div>
          
          {isLoading ? (
            <div className="dashboard-loading">{t("loading")}...</div>
          ) : (
            <>
              {/* Estadísticas */}
              <DashboardStats conversations={conversations} alertStats={alertStats} t={t} />
              
              {/* Botones de acción */}
              <div className="dashboard-actions">
                <button 
                  className="dashboard-button primary"
                  onClick={() => setShowTable(!showTable)}
                >
                  {showTable ? t("hide-table") : t("view-all-conversations")}
                </button>
                <button 
                  className="dashboard-button primary"
                  onClick={() => navigate("/dashboard/alerts")}
                >
                  {t("view-alerts")} {alertStats && alertStats.pending > 0 && `(${alertStats.pending})`}
                </button>
                {canManageAlertRules && (
                  <button 
                    className="dashboard-button primary"
                    onClick={() => navigate("/dashboard/alert-rules")}
                  >
                    {t("manage-alert-rules") || "Manage Alert Rules"}
                  </button>
                )}
                <button className="dashboard-button" disabled>
                  {t("create-users")} ({t("coming-soon")})
                </button>
              </div>

              {/* Tabla de conversaciones */}
              {showTable && (
                <div className="dashboard-table-container">
                  <ConversationsTable conversations={conversations || []} />
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </ProtectedRoute>
  );
}

// Componente de estadísticas
function DashboardStats({ 
  conversations, 
  alertStats, 
  t 
}: { 
  conversations: TConversation[]; 
  alertStats: TAlertStats | null;
  t: any;
}) {
  const totalConversations = conversations.length;
  const totalMessages = conversations.reduce((sum, conv) => sum + (conv.number_of_messages || 0), 0);
  const recentConversations = conversations.filter(conv => {
    const date = new Date(conv.created_at);
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    return date >= weekAgo;
  }).length;

  return (
    <div className="dashboard-stats">
      <div className="stat-card">
        <div className="stat-card-icon">💬</div>
        <div className="stat-card-content">
          <h3>{t("total-conversations")}</h3>
          <p className="stat-card-value">{totalConversations}</p>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-card-icon">📨</div>
        <div className="stat-card-content">
          <h3>{t("total-messages")}</h3>
          <p className="stat-card-value">{totalMessages}</p>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-card-icon">📅</div>
        <div className="stat-card-content">
          <h3>{t("this-week")}</h3>
          <p className="stat-card-value">{recentConversations}</p>
        </div>
      </div>
      {alertStats && (
        <>
          <div className="stat-card">
            <div className="stat-card-icon">⚠️</div>
            <div className="stat-card-content">
              <h3>{t("pending-alerts")}</h3>
              <p className="stat-card-value">{alertStats.pending}</p>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-card-icon">✅</div>
            <div className="stat-card-content">
              <h3>{t("resolved-alerts")}</h3>
              <p className="stat-card-value">{alertStats.resolved}</p>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-card-icon">🔔</div>
            <div className="stat-card-content">
              <h3>{t("total-alerts")}</h3>
              <p className="stat-card-value">{alertStats.total}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}