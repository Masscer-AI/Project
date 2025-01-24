import React, { useEffect, useState } from "react";
import "./Sidebar.css";
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
import { QRCodeDisplay } from "../QRGenerator/QRGenerator";

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
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

  const handleNewChat = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
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
      <div className="sidebar">
        <div className="flex-x justify-between">
          <a href="/chat" onClick={handleNewChat}>
            <SvgButton
              svg={SVGS.plus}
              size="big"
              extraClass="active-on-hover pressable justify-center"
              text={t("new-chat")}
            />
          </a>
          <SvgButton
            extraClass="active-on-hover pressable"
            onClick={toggleSidebar}
            svg={SVGS.burger}
          />
        </div>
        <div className="sidebar__history flex-y gap-small ">
          <SvgButton
            onClick={() =>
              setHistoryConfig((prev) => ({
                ...prev,
                isOpen: !prev.isOpen,
              }))
            }
            text={t("conversations")}
            svg={SVGS.chat}
            extraClass={` w-100 active-on-hover pressable ${historyConfig.isOpen ? "bg-active" : "bg-hovered"}`}
          />

          {historyConfig.isOpen && (
            <>
              {historyConfig.showFilters ? (
                <div className="conversation-history-filters">
                  <input
                    type="text"
                    className="input w-100 padding-medium"
                    placeholder={t("filter-conversations")}
                    autoFocus
                    name="conversation-filter"
                    value={filters.title}
                    onChange={(e) =>
                      setFilters({ ...filters, title: e.target.value })
                    }
                  />
                  <div className="date-filters d-flex gap-small">
                    <input
                      className="w-100 rounded padding-small"
                      type="date"
                      value={filters.startDate}
                      onChange={(e) =>
                        setFilters({ ...filters, startDate: e.target.value })
                      }
                    />
                    <input
                      className="w-100 rounded padding-small"
                      type="date"
                      value={filters.endDate}
                      onChange={(e) =>
                        setFilters({ ...filters, endDate: e.target.value })
                      }
                    />
                  </div>
                  <div className="d-flex gap-small">
                    <input
                      className="w-100 rounded padding-small"
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
                      className="w-100 rounded padding-small"
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
                  <div className="d-flex gap-small wrap-wrap">
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
                  <div className="d-flex gap-small">
                    <SvgButton
                      size="big"
                      text={t("clean-filters")}
                      extraClass="border-danger"
                      onClick={() => {
                        setFilters({
                          tags: [],
                          startDate: "",
                          endDate: "",
                          title: "",
                          minMessages: null,
                          maxMessages: null,
                        });
                        // setFilteredHistory(history);
                      }}
                    />
                    <SvgButton
                      size="big"
                      extraClass="border-gray"
                      text={t("close-filters")}
                      onClick={() =>
                        setHistoryConfig((prev) => ({
                          ...prev,
                          showFilters: false,
                        }))
                      }
                    />
                  </div>
                </div>
              ) : (
                <SvgButton
                  extraClass="border-gray"
                  text={t("show-filters")}
                  onClick={() =>
                    setHistoryConfig((prev) => ({
                      ...prev,
                      showFilters: true,
                    }))
                  }
                />
              )}
              <div className="flex-y conversation-history gap-small ">
                <h3>{t("today")}</h3>
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
                <h3>{t("previous-days")}</h3>
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
              <SvgButton
                svg={SVGS.tools}
                text={t("audio-tools")}
                size="big"
                extraClass="bg-hovered
          active-on-hover pressable w-100"
                onClick={() =>
                  setOpenedModals({ action: "add", name: "audio" })
                }
              />
              <SvgButton
                onClick={() => goTo("/whatsapp")}
                text={t("whatsapp")}
                size="big"
                extraClass="bg-hovered active-on-hover pressable w-100"
                svg={SVGS.whatsapp}
              />

              <SvgButton
                onClick={() => {
                  setOpenedModals({ action: "add", name: "documents" });
                  toggleSidebar();
                }}
                text={t("documents")}
                size="big"
                extraClass="bg-hovered active-on-hover pressable w-100"
                svg={SVGS.document}
              />
              <SvgButton
                onClick={() =>
                  setOpenedModals({ action: "add", name: "completions" })
                }
                text={t("completions")}
                size="big"
                extraClass="bg-hovered active-on-hover pressable w-100"
                svg={SVGS.question}
              />

              {/* <SvgButton
                text={t("workflows")}
                size="big"
                extraClass="bg-hovered active-on-hover pressable w-100"
                onClick={() => goTo("/workflows")}
                svg={SVGS.workflows}
              /> */}
            </>
          )}
        </div>
        <div className="sidebar__footer d-flex justify-between">
          <SvgButton
            onClick={openSettings}
            svg={SVGS.settings}
            title={t("settings")}
            extraClass="pressable active-on-hover "
            text={user ? user.username : t("you")}
          />
          <SvgButton
            onClick={logout}
            svg={SVGS.logout}
            title={t("logout")}
            extraClass="pressable danger-on-hover"
            confirmations={[t("sure?")]}
          />
        </div>
      </div>
      <div onClick={toggleSidebar} className="sidebar-backdrop"></div>
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
  const { setConversation, toggleSidebar } = useStore((state) => ({
    setConversation: state.setConversation,
    toggleSidebar: state.toggleSidebar,
  }));

  const { t } = useTranslation();

  const [showTrainingModal, setShowTrainingModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
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
  };

  return conversation.number_of_messages > 0 ? (
    <div className="conversation rounded-rect d-flex align-center">
      <p className="w-100" onClick={handleClick}>
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
          <SvgButton title={t("conversation-options")} svg={SVGS.options} />
        }
      >
        <div className="flex-y d-flex gap-small">
          <SvgButton
            size="big"
            svg={SVGS.trash}
            title={t("delete-conversation")}
            text={t("delete")}
            extraClass=" bg-danger"
            confirmations={[t("delete-conversation-confirmation")]}
            onClick={() => deleteConversationItem(conversation.id)}
          />
          <SvgButton
            extraClass=" bg-active"
            size="big"
            svg={SVGS.dumbell}
            title={t("train-on-this-conversation")}
            text={t("train")}
            onClick={() => setShowTrainingModal(true)}
          />
          <SvgButton
            extraClass=" bg-hovered"
            size="big"
            svg={SVGS.share}
            title={t("share-conversation")}
            text={t("share")}
            onClick={() => setShowShareModal(true)}
          />
          <div className="text-center">
            {conversation.number_of_messages} {t("messages")}
          </div>
          <div className="text-center">
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
