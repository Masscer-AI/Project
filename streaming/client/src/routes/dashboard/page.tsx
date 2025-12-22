import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { getAllConversations, getAlertStats, getUser } from "../../modules/apiCalls";
import { TConversation, TAlertStats } from "../../types";
import { TUserData } from "../../types/chatTypes";
import { ProtectedRoute } from "../../components/ProtectedRoute/ProtectedRoute";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { ConversationsTable } from "./ConversationsTable";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import "./page.css";

export default function DashboardPage() {
  const { chatState, startup, toggleSidebar, setUser } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
    toggleSidebar: state.toggleSidebar,
    setUser: state.setUser,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<TConversation[]>([]);
  const [alertStats, setAlertStats] = useState<TAlertStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showTable, setShowTable] = useState(false);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const canManageAlertRules = useIsFeatureEnabled("alert-rules-manager");

  useEffect(() => {
    const loadUser = async () => {
      try {
        const user = (await getUser()) as TUserData;
        setUser(user);
      } catch (error) {
        console.error("Error loading user:", error);
      }
    };
    
    loadUser();
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
              <h1 className="text-4xl font-bold mb-8 text-center text-white tracking-tight" style={{ textShadow: '0 2px 8px rgba(110, 91, 255, 0.2)' }}>
                {t("conversations-dashboard")}
              </h1>
            </div>
            
            {isLoading ? (
              <div className="text-center py-10 text-lg text-[rgb(156,156,156)]">
                {t("loading")}...
              </div>
            ) : (
              <>
                {/* Estadísticas */}
                <DashboardStats conversations={conversations} alertStats={alertStats} t={t} />
                
                {/* Botones de acción */}
                <div className="flex justify-center gap-4 mb-12 flex-wrap">
                  <button 
                    className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                      hoveredButton === 'table' 
                        ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                        : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                    }`}
                    style={{ transform: 'none' }}
                    onMouseEnter={() => setHoveredButton('table')}
                    onMouseLeave={() => setHoveredButton(null)}
                    onClick={() => setShowTable(!showTable)}
                  >
                    {showTable ? t("hide-table") : t("view-all-conversations")}
                  </button>
                  <button 
                    className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                      hoveredButton === 'alerts' 
                        ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                        : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                    }`}
                    style={{ transform: 'none' }}
                    onMouseEnter={() => setHoveredButton('alerts')}
                    onMouseLeave={() => setHoveredButton(null)}
                    onClick={() => navigate("/dashboard/alerts")}
                  >
                    {t("view-alerts")} {alertStats && alertStats.pending > 0 && `(${alertStats.pending})`}
                  </button>
                  {canManageAlertRules && (
                    <button 
                      className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                        hoveredButton === 'rules' 
                          ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                          : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                      }`}
                      style={{ transform: 'none' }}
                      onMouseEnter={() => setHoveredButton('rules')}
                      onMouseLeave={() => setHoveredButton(null)}
                      onClick={() => navigate("/dashboard/alert-rules")}
                    >
                      {t("manage-alert-rules")}
                    </button>
                  )}
                  <button 
                    className="px-8 py-3 rounded-full font-normal text-sm cursor-not-allowed border bg-[rgba(35,33,39,0.3)] text-[rgb(156,156,156)] border-[rgba(156,156,156,0.2)] opacity-50"
                    style={{ transform: 'none' }}
                    disabled
                  >
                    {t("create-users")} ({t("coming-soon")})
                  </button>
                </div>

                {/* Tabla de conversaciones */}
                {showTable && (
                  <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 shadow-lg">
                    <ConversationsTable conversations={conversations || []} />
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>
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
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
      <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 flex items-center gap-4 shadow-lg">
        <div className="text-4xl">💬</div>
        <div className="flex-1">
          <h3 className="text-sm font-medium text-[rgb(156,156,156)] mb-2 uppercase tracking-wide">{t("total-conversations")}</h3>
          <p className="text-3xl font-bold text-white">{totalConversations}</p>
        </div>
      </div>
      <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 flex items-center gap-4 shadow-lg">
        <div className="text-4xl">📨</div>
        <div className="flex-1">
          <h3 className="text-sm font-medium text-[rgb(156,156,156)] mb-2 uppercase tracking-wide">{t("total-messages")}</h3>
          <p className="text-3xl font-bold text-white">{totalMessages}</p>
        </div>
      </div>
      <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 flex items-center gap-4 shadow-lg">
        <div className="text-4xl">📅</div>
        <div className="flex-1">
          <h3 className="text-sm font-medium text-[rgb(156,156,156)] mb-2 uppercase tracking-wide">{t("this-week")}</h3>
          <p className="text-3xl font-bold text-white">{recentConversations}</p>
        </div>
      </div>
      {alertStats && (
        <>
          <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 flex items-center gap-4 shadow-lg">
            <div className="text-4xl">⚠️</div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-[rgb(156,156,156)] mb-2 uppercase tracking-wide">{t("pending-alerts")}</h3>
              <p className="text-3xl font-bold text-white">{alertStats.pending}</p>
            </div>
          </div>
          <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 flex items-center gap-4 shadow-lg">
            <div className="text-4xl">✅</div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-[rgb(156,156,156)] mb-2 uppercase tracking-wide">{t("resolved-alerts")}</h3>
              <p className="text-3xl font-bold text-white">{alertStats.resolved}</p>
            </div>
          </div>
          <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 flex items-center gap-4 shadow-lg">
            <div className="text-4xl">🔔</div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-[rgb(156,156,156)] mb-2 uppercase tracking-wide">{t("total-alerts")}</h3>
              <p className="text-3xl font-bold text-white">{alertStats.total}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}