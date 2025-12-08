import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { getAllConversations } from "../../modules/apiCalls";
import { TConversation } from "../../types";
import { ProtectedRoute } from "../../components/ProtectedRoute/ProtectedRoute";
import { useTranslation } from "react-i18next";
import { ConversationsTable } from "./ConversationsTable";
import "./page.css";

export default function DashboardPage() {
  const { chatState, startup } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
  }));
  const { t } = useTranslation();
  const [conversations, setConversations] = useState<TConversation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    startup();
    loadConversations();
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
              <DashboardStats conversations={conversations} t={t} />
              
              {/* Botones de acción */}
              <div className="dashboard-actions">
                <button 
                  className="dashboard-button primary"
                  onClick={() => setShowTable(!showTable)}
                >
                  {showTable ? t("hide-table") : t("view-all-conversations")}
                </button>
                <button className="dashboard-button" disabled>
                  {t("alerts")} ({t("coming-soon")})
                </button>
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
function DashboardStats({ conversations, t }: { conversations: TConversation[]; t: any }) {
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
    </div>
  );
}