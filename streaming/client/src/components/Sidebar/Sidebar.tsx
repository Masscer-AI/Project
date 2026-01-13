import React, { useEffect, useState } from "react";
import { SVGS } from "../../assets/svgs";
import { useStore } from "../../modules/store";
import { useSearchParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { SvgButton } from "../SvgButton/SvgButton";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import {
  deleteConversation,
  generateTrainingCompletions,
  getAllConversations,
  shareConversation,
} from "../../modules/apiCalls";
import { TConversation } from "../../types";
import { Modal } from "../Modal/Modal";
import toast from "react-hot-toast";
import { Pill } from "../Pill/Pill";
import { useTranslation } from "react-i18next";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { QRCodeDisplay } from "../QRGenerator/QRGenerator";

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const isConversationsDashboardEnabled = useIsFeatureEnabled("conversations-dashboard");
  const {
    toggleSidebar,
    setConversation,
    user,
    setOpenedModals,
    logout,
    userTags,
  } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    setConversation: state.setConversation,
    user: state.user,
    setOpenedModals: state.setOpenedModals,
    logout: state.logout,
    userTags: state.userTags,
  }));

  const [history, setHistory] = useState<TConversation[]>([]);
  const [filteredHistory, setFilteredHistory] = useState<TConversation[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [historyConfig, setHistoryConfig] = useState<{
    isOpen: boolean;
    showFilters: boolean;
  }>({
    isOpen: false,
    showFilters: false,
  });

  const [filters, setFilters] = useState<{
    tags: string[];
    startDate: string;
    endDate: string;
    title: string;
    minMessages: number | null;
    maxMessages: number | null;
  }>({
    tags: [],
    startDate: "",
    endDate: "",
    title: "",
    minMessages: null,
    maxMessages: null,
  });

  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    populateHistory();
  }, []);

  useEffect(() => {
    let filteredHistory = filterByDateRange();

    if (filters.tags.length > 0) {
      filteredHistory = filteredHistory.filter((c) =>
        c.tags?.some((tag) => filters.tags.includes(tag))
      );
    }

    filteredHistory = filteredHistory.filter(
      (c) =>
        c.title && c.title.toLowerCase().includes(filters.title.toLowerCase())
    );

    filteredHistory = filteredHistory.filter(
      (c) =>
        c.number_of_messages >= (filters.minMessages || 0) &&
        c.number_of_messages <= (filters.maxMessages || 100000)
    );

    setFilteredHistory(filteredHistory);
  }, [filters]);

  const populateHistory = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      console.error("No token found in localStorage");
      return;
    }

    try {
      const res = await getAllConversations();
      setHistory(res);
      setFilteredHistory(res);
    } catch (error) {
      console.error("Failed to fetch conversations in sidebar", error);
    }
  };

  const handleNewChat = () => {
    setConversation(null);
    if (searchParams.has("conversation")) {
      searchParams.delete("conversation");
      setSearchParams(searchParams);
    }
    toggleSidebar();
    navigate(`/chat`);
  };

  const goTo = (to: string) => {
    navigate(to);
  };

  const deleteConversationItem = async (id: string) => {
    setHistory(history.filter((conversation) => conversation.id !== id));
    setFilteredHistory(
      filteredHistory.filter((conversation) => conversation.id !== id)
    );
    const res = await deleteConversation(id);
  };

  const openSettings = () => {
    setOpenedModals({ action: "add", name: "settings" });
    toggleSidebar();
  };

  // Function to filter based on date range
  const filterByDateRange = () => {
    return history.filter((c) => {
      const createdAtDate = new Date(c.created_at);
      // add one day to start and end date to include the whole day

      const start = filters.startDate ? new Date(filters.startDate) : null;
      if (start) {
        // Add one day to start date to include the whole day
        start.setDate(start.getDate() + 1);
        start.setHours(0, 0, 0, 0);
      }

      const end = filters.endDate ? new Date(filters.endDate) : new Date();
      if (end) {
        // Add one day to end date to include the whole day
        end.setDate(end.getDate() + 1);
        end.setHours(23, 59, 59, 999);
      }

      const letPass =
        (!start || createdAtDate >= start) && createdAtDate <= end;
      // if (letPass) {
      //   console.table({ startDate, start, endDate, end, createdAtDate });
      // }

      return letPass;
    });
  };

  const filterByTag = (tag: string) => {
    // Remove the tag from the filters if it is already in the filters, otherwise add it
    setFilters((prev) => ({
      ...prev,
      tags: prev.tags.includes(tag)
        ? prev.tags.filter((t) => t !== tag)
        : [...prev.tags, tag],
    }));
  };

  const today = new Date().toLocaleDateString();

  return (
    <>
      <div className="bg-[rgba(35,33,39,0.5)] backdrop-blur-md fixed md:relative left-0 top-0 h-screen z-[50] md:z-[3] flex flex-col w-[min(350px,100%)] p-3 gap-2.5 border-r border-[rgba(255,255,255,0.1)] animate-[appear-left_500ms_forwards] md:[animation:none]">
        <div className="flex justify-between gap-2">
          <button
            className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
              hoveredButton === 'new-chat' 
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('new-chat')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={handleNewChat}
          >
            <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.plus}</div>
            <span>{t("new-chat")}</span>
          </button>
          <button
            className={`px-4 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
              hoveredButton === 'burger' 
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('burger')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={toggleSidebar}
          >
            <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.burger}</div>
          </button>
        </div>
        <div className="[scrollbar-width:none] overflow-auto p-0.5 flex flex-col gap-2.5 flex-1">
          <button
            className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
              hoveredButton === 'conversations' || historyConfig.isOpen
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('conversations')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={() =>
              setHistoryConfig((prev) => ({
                ...prev,
                isOpen: !prev.isOpen,
              }))
            }
          >
            <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.chat}</div>
            <span>{t("conversations")}</span>
          </button>

          {historyConfig.isOpen && (
            <>
              {historyConfig.showFilters ? (
                <div className="flex flex-col gap-2.5">
                  <input
                    type="text"
                    className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
                    placeholder={t("filter-conversations")}
                    autoFocus
                    name="conversation-filter"
                    value={filters.title}
                    onChange={(e) =>
                      setFilters({ ...filters, title: e.target.value })
                    }
                  />
                  <div className="flex gap-2.5">
                    <input
                      className="w-full rounded-lg p-2 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] text-white focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
                      type="date"
                      value={filters.startDate}
                      onChange={(e) =>
                        setFilters({ ...filters, startDate: e.target.value })
                      }
                    />
                    <input
                      className="w-full rounded-lg p-2 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] text-white focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
                      type="date"
                      value={filters.endDate}
                      onChange={(e) =>
                        setFilters({ ...filters, endDate: e.target.value })
                      }
                    />
                  </div>
                  <div className="flex gap-2.5">
                    <input
                      className="w-full rounded-lg p-2 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
                      type="number"
                      min={0}
                      placeholder={t("min-messages")}
                      value={filters.minMessages || ""}
                      onChange={(e) =>
                        setFilters({
                          ...filters,
                          minMessages: e.target.value
                            ? parseInt(e.target.value)
                            : null,
                        })
                      }
                    />
                    <input
                      className="w-full rounded-lg p-2 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
                      type="number"
                      placeholder={t("max-messages")}
                      min={0}
                      value={filters.maxMessages || ""}
                      onChange={(e) =>
                        setFilters({
                          ...filters,
                          maxMessages: e.target.value
                            ? parseInt(e.target.value)
                            : null,
                        })
                      }
                    />
                  </div>
                  <div className="flex gap-2.5 flex-wrap">
                    {userTags.map((tag) => (
                      <Pill
                        onClick={() => filterByTag(tag)}
                        extraClass={`${filters.tags.includes(tag) ? "bg-active" : "bg-hovered"}`}
                        key={tag}
                      >
                        {tag}
                      </Pill>
                    ))}
                  </div>
                  <div className="flex gap-2.5">
                    <button
                      className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
                        hoveredButton === 'clean-filters' 
                          ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                          : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                      }`}
                      style={{ transform: 'none' }}
                      onMouseEnter={() => setHoveredButton('clean-filters')}
                      onMouseLeave={() => setHoveredButton(null)}
                      onClick={() => {
                        setFilters({
                          tags: [],
                          startDate: "",
                          endDate: "",
                          title: "",
                          minMessages: null,
                          maxMessages: null,
                        });
                      }}
                    >
                      {t("clean-filters")}
                    </button>
                    <button
                      className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
                        hoveredButton === 'close-filters' 
                          ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                          : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                      }`}
                      style={{ transform: 'none' }}
                      onMouseEnter={() => setHoveredButton('close-filters')}
                      onMouseLeave={() => setHoveredButton(null)}
                      onClick={() =>
                        setHistoryConfig((prev) => ({
                          ...prev,
                          showFilters: false,
                        }))
                      }
                    >
                      {t("close-filters")}
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
                    hoveredButton === 'show-filters' 
                      ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                      : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                  }`}
                  style={{ transform: 'none' }}
                  onMouseEnter={() => setHoveredButton('show-filters')}
                  onMouseLeave={() => setHoveredButton(null)}
                  onClick={() =>
                    setHistoryConfig((prev) => ({
                      ...prev,
                      showFilters: true,
                    }))
                  }
                >
                  {t("show-filters")}
                </button>
              )}
              <div className="h-full overflow-y-auto [scrollbar-width:none] flex flex-col gap-2.5">
                <h3 className="text-white font-semibold text-sm">{t("today")}</h3>
                {filteredHistory
                  .filter(
                    (c) => new Date(c.created_at).toLocaleDateString() === today
                  )
                  .map((conversation) => (
                    <ConversationComponent
                      key={conversation.id}
                      conversation={conversation}
                      deleteConversationItem={deleteConversationItem}
                    />
                  ))}
                <h3 className="text-white font-semibold text-sm">{t("previous-days")}</h3>
                {filteredHistory
                  .filter(
                    (c) => new Date(c.created_at).toLocaleDateString() !== today
                  )
                  .map((conversation) => (
                    <ConversationComponent
                      key={conversation.id}
                      conversation={conversation}
                      deleteConversationItem={deleteConversationItem}
                    />
                  ))}
              </div>
            </>
          )}

          {!historyConfig.isOpen && (
            <>
              <button
                className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                  hoveredButton === 'audio-tools' 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onMouseEnter={() => setHoveredButton('audio-tools')}
                onMouseLeave={() => setHoveredButton(null)}
                onClick={() =>
                  setOpenedModals({ action: "add", name: "audio" })
                }
              >
                <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.tools}</div>
                <span>{t("audio-tools")}</span>
              </button>
              <button
                className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                  hoveredButton === 'whatsapp' 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onMouseEnter={() => setHoveredButton('whatsapp')}
                onMouseLeave={() => setHoveredButton(null)}
                onClick={() => goTo("/whatsapp")}
              >
                <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.whatsapp}</div>
                <span>{t("whatsapp")}</span>
              </button>
              <button
                className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                  hoveredButton === 'documents' 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onMouseEnter={() => setHoveredButton('documents')}
                onMouseLeave={() => setHoveredButton(null)}
                onClick={() => {
                  setOpenedModals({ action: "add", name: "documents" });
                  toggleSidebar();
                }}
              >
                <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.document}</div>
                <span>{t("documents")}</span>
              </button>
              <button
                className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                  hoveredButton === 'completions' 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onMouseEnter={() => setHoveredButton('completions')}
                onMouseLeave={() => setHoveredButton(null)}
                onClick={() =>
                  setOpenedModals({ action: "add", name: "completions" })
                }
              >
                <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.question}</div>
                <span>{t("completions")}</span>
              </button>
              {isConversationsDashboardEnabled && (
                <button
                  className={`w-full px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                    hoveredButton === 'dashboard' 
                      ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                      : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                  }`}
                  style={{ transform: 'none' }}
                  onMouseEnter={() => setHoveredButton('dashboard')}
                  onMouseLeave={() => setHoveredButton(null)}
                  onClick={() => goTo("/dashboard")}
                >
                  <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.chat}</div>
                  <span>{t("conversations-dashboard")}</span>
                </button>
              )}
            </>
          )}
        </div>
        <div className="mt-auto flex justify-between gap-2">
          <button
            className={`flex-1 px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
              hoveredButton === 'settings' 
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('settings')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={openSettings}
            title={t("settings")}
          >
            <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.settings}</div>
            <span>{user ? user.username : t("you")}</span>
          </button>
          <button
            className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
              hoveredButton === 'logout' 
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('logout')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={logout}
            title={t("logout")}
          >
            <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">{SVGS.logout}</div>
          </button>
        </div>
      </div>
      <div onClick={toggleSidebar} className="bg-[rgba(55,55,55,0.52)] w-screen h-screen fixed top-0 left-0 z-[40] md:hidden"></div>
    </>
  );
};

const ConversationComponent = ({
  conversation,
  deleteConversationItem,
}: {
  conversation: TConversation;
  deleteConversationItem: (id: string) => void;
}) => {
  const [_, setSearchParams] = useSearchParams();
  const { setConversation, toggleSidebar, chatState } = useStore((state) => ({
    setConversation: state.setConversation,
    toggleSidebar: state.toggleSidebar,
    chatState: state.chatState,
  }));

  const { t } = useTranslation();

  const [showTrainingModal, setShowTrainingModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleClick = () => {
    console.log("Conversation clicked", conversation.id, "Trying to open");
    setConversation(conversation.id);

    const queryParams = {
      conversation: conversation.id,
    };
    setSearchParams(queryParams);
    console.log("Navigating to", `/chat?conversation=${conversation.id}`);
    navigate(`/chat?conversation=${conversation.id}`);
    
    // Cerrar el sidebar en mobile después de seleccionar una conversación
    if (window.innerWidth < 768 && chatState.isSidebarOpened) {
      toggleSidebar();
    }
  };

  return conversation.number_of_messages > 0 ? (
    <div className="flex items-center justify-between text-[17.5px] cursor-pointer relative text-ellipsis whitespace-nowrap p-0 rounded-lg hover:bg-[rgba(255,255,255,0.05)] transition-colors">
      <p className="w-full p-2.5 max-w-full overflow-hidden" onClick={handleClick}>
        {(conversation.title || conversation.id).slice(0, 30)}
      </p>
      {showTrainingModal && (
        <TrainingOnConversation
          conversation={conversation}
          hide={() => setShowTrainingModal(false)}
        />
      )}
      {showShareModal && (
        <ShareConversationModal
          hide={() => setShowShareModal(false)}
          conversationId={conversation.id}
        />
      )}
      <FloatingDropdown
        right="100%"
        top="0"
        opener={
          <SvgButton 
            title={t("conversation-options")} 
            svg={SVGS.options}
            extraClass="hover:!bg-white hover:!border-white [&>svg]:hover:!fill-black [&>svg]:hover:!stroke-black [&>svg>*]:hover:!fill-black [&>svg>*]:hover:!stroke-black"
          />
        }
      >
        <div className="w-[200px] flex flex-col gap-3 p-4 bg-black/95 backdrop-blur-sm border border-gray-700 rounded-2xl shadow-lg">
          <button
            className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
              hoveredButton === 'delete'
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]'
                : 'bg-[#dc2626] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#b91c1c]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('delete')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={() => deleteConversationItem(conversation.id)}
          >
            <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.trash}</span>
            <span>{t("delete")}</span>
          </button>
          <button
            className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
              hoveredButton === 'train'
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]'
                : 'bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('train')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={() => setShowTrainingModal(true)}
          >
            <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.dumbell}</span>
            <span>{t("train")}</span>
          </button>
          <button
            className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
              hoveredButton === 'share'
                ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]'
                : 'bg-[#232127] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#1a181d]'
            }`}
            style={{ transform: 'none' }}
            onMouseEnter={() => setHoveredButton('share')}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={() => setShowShareModal(true)}
          >
            <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.share}</span>
            <span>{t("share")}</span>
          </button>
          <div className="text-center text-gray-300 text-sm">
            {conversation.number_of_messages} {t("messages")}
          </div>
          <div className="text-center text-gray-300 text-sm">
            {new Date(conversation.created_at).toLocaleString()}
          </div>
        </div>
      </FloatingDropdown>
    </div>
  ) : null;
};

const ShareConversationModal = ({ hide, conversationId }) => {
  const [validUntil, setValidUntil] = useState(null as Date | null);
  const { t } = useTranslation();
  const [sharedId, setSharedId] = useState("");

  const share = async () => {
    const tid = toast.loading(t("sharing-conversation"));
    try {
      const res = await shareConversation(conversationId, validUntil);
      toast.dismiss(tid);
      setSharedId(res.id);
    } catch (e) {
      console.error("Failed to share conversation", e);
      toast.dismiss(tid);
      toast.error(t("failed-to-share-conversation"));
    }
  };

  const formatDateToLocalString = (date) => {
    return date.toISOString().slice(0, 16);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success(t("copied-to-clipboard"));
  };

  const generateShareLink = () => {
    return `${window.location.origin}/s?id=${sharedId}`;
  };

  const openLink = () => {
    const url = generateShareLink();
    window.open(url, "_blank");
  };

  return (
    <Modal minHeight={"fit-content"} hide={hide}>
      <div className="d-flex flex-y">
        {!sharedId && (
          <>
            <div className="flex-y gap-big">
              <h2 className="text-center padding-big">
                {t("share-conversation")}
              </h2>
              <p>{t("share-conversation-description")}</p>
              <input
                type="datetime-local"
                className="input padding-big"
                defaultValue={
                  validUntil ? formatDateToLocalString(validUntil) : ""
                }
                onChange={(e) => setValidUntil(new Date(e.target.value))}
              />
              <SvgButton
                svg={SVGS.share}
                text={t("share-now")}
                size="big"
                onClick={share}
              />
            </div>
          </>
        )}
        {sharedId && (
          <div className="d-flex flex-y gap-big">
            <h2 className="text-center padding-big bg-success-opaque rounded">
              {t("conversation-shared-message")}
            </h2>
            <div className="d-flex justify-center qr-display">
              <QRCodeDisplay size={256} url={generateShareLink()} />
            </div>
            <input
              type="text"
              value={generateShareLink()}
              className="w-100 input padding-big bg-hovered"
            />
            <div className="d-flex gap-small ">
              <SvgButton
                extraClass="bg-hovered active-on-hover"
                onClick={() => copyToClipboard(generateShareLink())}
                svg={SVGS.copy}
                text={t("copy")}
                size="big"
              />
              <SvgButton
                extraClass="bg-hovered active-on-hover"
                onClick={openLink}
                svg={SVGS.redirect}
                text={t("open-link")}
                size="big"
              />
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

const TrainingOnConversation = ({
  hide,
  conversation,
}: {
  hide: () => void;
  conversation: TConversation;
}) => {
  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
  };

  const { t } = useTranslation();

  const { agents } = useStore((state) => ({
    agents: state.agents,
  }));

  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [completionsTargetNumber, setCompletionsTargetNumber] = useState(30);
  const toggleAgent = (slug: string) => {
    if (selectedAgents.includes(slug)) {
      setSelectedAgents((prev) => prev.filter((s) => s !== slug));
    } else {
      setSelectedAgents((prev) => [...prev, slug]);
    }
  };

  const generateTrainingData = async () => {
    if (selectedAgents.length === 0) {
      toast.error(t("please-select-at-least-one-agent"));
    }

    const res = await generateTrainingCompletions({
      model_id: conversation.id,
      db_model: "conversation",
      agents: selectedAgents,
      completions_target_number: completionsTargetNumber,
    });
    toast.success(t("training-generation-in-queue"));
    hide();
  };

  return (
    <Modal minHeight={"40vh"} hide={hide}>
      <div className="d-flex flex-y gap-big">
        <h2 className="text-center">{t("generate-completions")}</h2>
        <p>
          {t("generate-completions-description")}{" "}
          <strong>{conversation.title}</strong>{" "}
          {t("generate-completions-description-2")}
        </p>
        <p>{t("after-generating-completions")}</p>
        <form onSubmit={onSubmit} action="">
          <label>
            {t("number-of-completions-to-generate")}
            <input
              className="input"
              type="number"
              defaultValue={30}
              onChange={(e) =>
                setCompletionsTargetNumber(parseInt(e.target.value))
              }
            />
          </label>
          <p>{t("select-agents-that-will-retrain")}</p>
          <div className="d-flex gap-small wrap-wrap padding-medium">
            {agents.map((a) => (
              <Pill
                extraClass={`${selectedAgents.includes(a.slug) ? "bg-active" : "bg-hovered"}`}
                key={a.id}
                onClick={() => toggleAgent(a.slug)}
              >
                {a.name}
              </Pill>
            ))}
          </div>
        </form>
        <SvgButton
          svg={SVGS.dumbell}
          text="Generate"
          size="big"
          onClick={generateTrainingData}
        />
      </div>
    </Modal>
  );
};
