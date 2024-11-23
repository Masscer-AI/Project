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
  // const [relatedAgents, setRelatedAgents] = useState<string[]>([]);

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
    <>
      <div className="sidebar">
        <div className="flex-x justify-between">
          <SvgButton
            onClick={handleNewChat}
            svg={SVGS.plus}
            size="big"
            extraClass="active-on-hover pressable"
            text={t("new-chat")}
          />
          <SvgButton
            extraClass="active-on-hover pressable"
            onClick={toggleSidebar}
            svg={SVGS.burger}
          />
        </div>
        <div className="sidebar__history flex-y gap-small ">
          <SvgButton
            onClick={() => handleSectionClick("conversations")}
            text={t("conversations")}
            svg={SVGS.chat}
            extraClass={` w-100 active-on-hover pressable ${openedSections.includes("conversations") ? "bg-active" : "bg-hovered"}`}
          />

          {openedSections.includes("conversations") && (
            <>
              <input
                type="text"
                className="input w-100 padding-medium"
                placeholder={t("filter-conversations")}
                autoFocus
                name="conversation-filter"
                value={conversationFilter}
                onChange={(e) => setConversationFilter(e.target.value)}
              />
              <div className="flex-y conversation-history gap-small ">
                {filteredHistory.map((conversation) => (
                  <ConversationComponent
                    key={conversation.id}
                    conversation={conversation}
                    deleteConversationItem={deleteConversationItem}
                  />
                ))}
              </div>
            </>
          )}

          <SvgButton
            svg={SVGS.tools}
            text={t("tools")}
            size="big"
            extraClass="bg-hovered
          active-on-hover pressable w-100"
            onClick={() => goTo("/tools")}
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

          <SvgButton
            text={t("workflows")}
            size="big"
            extraClass="bg-hovered active-on-hover pressable w-100"
            onClick={() => goTo("/workflows")}
            svg={SVGS.workflows}
          />
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
  const [searchParams, setSearchParams] = useSearchParams();
  const { setConversation, toggleSidebar } = useStore((state) => ({
    setConversation: state.setConversation,
    toggleSidebar: state.toggleSidebar,
  }));

  const { t } = useTranslation();

  // console.log(conversation, "conversation");

  const [showTrainingModal, setShowTrainingModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const navigate = useNavigate();

  const handleClick = () => {
    console.log("Conversation clicked", conversation.id, "Trying to open");
    setConversation(conversation.id);
    toggleSidebar();
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
            extraClass="justify-between bg-danger"
            confirmations={[t("delete-conversation-confirmation")]}
            onClick={() => deleteConversationItem(conversation.id)}
          />
          <SvgButton
            extraClass="justify-between bg-active"
            size="big"
            svg={SVGS.dumbell}
            title={t("train-on-this-conversation")}
            text={t("train")}
            onClick={() => setShowTrainingModal(true)}
          />
          <SvgButton
            extraClass="justify-between bg-hovered"
            size="big"
            svg={SVGS.share}
            title={t("share-conversation")}
            text={t("share")}
            onClick={() => setShowShareModal(true)}
          />
          <div className="text-center">
            {conversation.number_of_messages} {t("messages")}
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
