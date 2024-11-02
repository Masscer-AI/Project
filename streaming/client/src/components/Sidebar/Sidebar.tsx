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
} from "../../modules/apiCalls";
import { TConversation } from "../../types";
import { Modal } from "../Modal/Modal";
import { AgentSelector } from "../AgentSelector/AgentSelector";
import toast from "react-hot-toast";
import { Pill } from "../Pill/Pill";
import { LanguageSelector } from "../LanguageSelector/LanguageSelector";
import { useTranslation } from "react-i18next";

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const { toggleSidebar, setConversation, user, setOpenedModals } = useStore(
    (state) => ({
      toggleSidebar: state.toggleSidebar,
      setConversation: state.setConversation,
      user: state.user,
      setOpenedModals: state.setOpenedModals,
    })
  );

  const [history, setHistory] = useState<TConversation[]>([]);
  const [filteredHistory, setFilteredHistory] = useState<TConversation[]>([]);
  const [conversationFilter, setConversationFilter] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const [openedSections, setOpenedSections] = useState<string[]>([]);

  const navigate = useNavigate();

  useEffect(() => {
    populateHistory();
  }, []);

  useEffect(() => {
    setFilteredHistory(
      history.filter(
        (c) =>
          c.title &&
          c.title.toLowerCase().includes(conversationFilter.toLowerCase())
      )
    );
  }, [conversationFilter]);

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
      console.error("Failed to fetch conversations", error);
    }
  };

  const handleNewChat = () => {
    setConversation(null);
    if (searchParams.has("conversation")) {
      searchParams.delete("conversation");
      setOpenedModals({ action: "add", name: "settings" });
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

  const handleSectionClick = (section: string) => {
    if (openedSections.includes(section)) {
      setOpenedSections((prev) => prev.filter((s) => s !== section));
    } else {
      setOpenedSections((prev) => [...prev, section]);
    }
  };

  const openSettings = () => {
    setOpenedModals({ action: "add", name: "settings" });
    toggleSidebar();
  };

  return (
    <div className="sidebar">
      <div className="sidebar__header">
        <SvgButton
          onClick={handleNewChat}
          svg={SVGS.plus}
          size="big"
          text={t("new-chat")}
        />
        <SvgButton onClick={toggleSidebar} svg={SVGS.burger} />
      </div>
      <div className="sidebar__history">
        <h3
          className={`button ${openedSections.includes("conversations") ? "bg-hovered" : ""}`}
          onClick={() => handleSectionClick("conversations")}
        >
          {t("conversations")}
        </h3>
        {openedSections.includes("conversations") && (
          <>
            <input
              type="text"
              className="input w-100 padding-medium"
              placeholder={t("filter-conversations")}
              autoFocus
              value={conversationFilter}
              onChange={(e) => setConversationFilter(e.target.value)}
            />
            {filteredHistory.map((conversation) => (
              <ConversationComponent
                key={conversation.id}
                conversation={conversation}
                deleteConversationItem={deleteConversationItem}
              />
            ))}
          </>
        )}
      </div>
      <div>
        <h3
          className={`button ${openedSections.includes("tools") ? "bg-hovered" : ""}`}
          onClick={() => handleSectionClick("tools")}
        >
          {t("tools")}
        </h3>
        {openedSections.includes("tools") && (
          <>
            <p
              className="clickeable rounded-rect"
              onClick={() => goTo("/tools?selected=audio")}
            >
              {t("audio")}
            </p>
            <p
              className="clickeable rounded-rect"
              onClick={() => goTo("/tools?selected=images")}
            >
              {t("images")}
            </p>
            <p
              className="clickeable rounded-rect"
              onClick={() => goTo("/tools?selected=video")}
            >
              {t("video")}
            </p>
            <p
              className="clickeable rounded-rect"
              onClick={() => goTo("/whatsapp")}
            >
              {t("whatsapp")}
            </p>
          </>
        )}
      </div>
      <div>
        <h3
          className={`button ${openedSections.includes("training") ? "bg-hovered" : ""}`}
          onClick={() => handleSectionClick("training")}
        >
          {t("training")}
        </h3>
        {openedSections.includes("training") && (
          <>
            <p
              className="clickeable rounded-rect"
              onClick={() => {
                setOpenedModals({ action: "add", name: "documents" });
                toggleSidebar();
              }}
            >
              {t("documents")}
            </p>

            <p
              className="clickeable rounded-rect"
              onClick={() =>
                setOpenedModals({ action: "add", name: "completions" })
              }
            >
              {t("completions")}
            </p>
            <p
              className="clickeable rounded-rect"
              onClick={() => setOpenedModals({ action: "add", name: "tags" })}
            >
              {t("tags")}
            </p>
          </>
        )}
      </div>
      <div className="sidebar__footer d-flex justify-between">
        <SvgButton text={user ? user.username : t("you")} />
        <SvgButton
          onClick={openSettings}
          svg={SVGS.controls}
          text={t("settings")}
        />
      </div>
    </div>
  );
};

const ConversationComponent = ({
  conversation,
  deleteConversationItem,
}: {
  conversation: TConversation;
  deleteConversationItem: (id: string) => void;
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { setConversation, toggleSidebar } = useStore((state) => ({
    setConversation: state.setConversation,
    toggleSidebar: state.toggleSidebar,
  }));

  const { t } = useTranslation();

  const [showTrainingModal, setShowTrainingModal] = useState(false);
  const navigate = useNavigate();

  const handleClick = (e) => {
    e.preventDefault();
    setConversation(conversation.id);
    toggleSidebar();
    const queryParams = {
      conversation: conversation.id,
    };
    setSearchParams(queryParams);

    navigate(`/chat?conversation=${conversation.id}`);
  };

  return (
    <>
      {conversation.number_of_messages > 0 ? (
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
          <div className="conversation__options">
            <FloatingDropdown
              right="100%"
              opener={
                <SvgButton
                  title={t("conversation-options")}
                  svg={SVGS.options}
                />
              }
            >
              <SvgButton
                size="big"
                svg={SVGS.trash}
                title={t("delete-conversation")}
                text={t("delete")}
                confirmations={[t("delete-conversation-confirmation")]}
                onClick={() => deleteConversationItem(conversation.id)}
                extraClass="bg-danger"
              />
              <SvgButton
                size="big"
                svg={SVGS.dumbell}
                title={t("train-on-this-conversation")}
                text={t("train")}
                onClick={() => setShowTrainingModal(true)}
              />
            </FloatingDropdown>
          </div>
        </div>
      ) : null}
    </>
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
        <h2 className="text-center">{t("generate-completions25%")}</h2>
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
