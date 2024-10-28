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

export const Sidebar: React.FC = () => {
  const { toggleSidebar, setConversation, user, setOpenedModals } = useStore(
    (state) => ({
      toggleSidebar: state.toggleSidebar,
      setConversation: state.setConversation,
      user: state.user,
      setOpenedModals: state.setOpenedModals,
    })
  );

  const [history, setHistory] = useState<TConversation[]>([]);

  const [searchParams, setSearchParams] = useSearchParams();
  const [openedSections, setOpenedSections] = useState<string[]>([]);

  const navigate = useNavigate();

  useEffect(() => {
    populateHistory();
  }, []);

  const populateHistory = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      console.error("No token found in localStorage");
      return;
    }

    try {
      const res = await getAllConversations();
      setHistory(res);
    } catch (error) {
      console.error("Failed to fetch conversations", error);
    }
  };

  const handleNewChat = () => {
    setConversation(null);
    if (searchParams.has("conversation")) {
      searchParams.delete("conversation");
      setSearchParams(searchParams);
    } else {
      console.log("Starting a new chat...");
    }
    toggleSidebar();

    navigate(`/chat`);
  };

  const goTo = (to: string) => {
    navigate(to);
  };

  const deleteConversationItem = async (id: string) => {
    setHistory(history.filter((conversation) => conversation.id !== id));
    const res = await deleteConversation(id);
    console.log(res);
  };

  const handleSectionClick = (section: string) => {
    if (openedSections.includes(section)) {
      setOpenedSections((prev) => prev.filter((s) => s !== section));
    } else {
      setOpenedSections((prev) => [...prev, section]);
    }
  };

  return (
    <div className="sidebar">
      <div className="sidebar__header">
        <SvgButton
          onClick={handleNewChat}
          svg={SVGS.plus}
          size="big"
          text="New Chat"
        />
        <SvgButton onClick={toggleSidebar} svg={SVGS.burger} />
      </div>
      <div className="sidebar__history">
        <h3
          className={`button ${openedSections.includes("conversations") ? "bg-hovered" : ""}`}
          onClick={() => handleSectionClick("conversations")}
        >
          Conversations
        </h3>
        {openedSections.includes("conversations") &&
          history.map((conversation) => (
            <ConversationComponent
              key={conversation.id}
              conversation={conversation}
              deleteConversationItem={deleteConversationItem}
            />
          ))}
      </div>
      <div>
        <h3
          className={`button ${openedSections.includes("tools") ? "bg-hovered" : ""}`}
          onClick={() => handleSectionClick("tools")}
        >
          Tools
        </h3>
        {openedSections.includes("tools") && (
          <>
            <p
              className="clickeable rounded-rect"
              onClick={() => goTo("/tools?selected=audio")}
            >
              Audio
            </p>
            <p
              className="clickeable rounded-rect"
              onClick={() => goTo("/tools?selected=images")}
            >
              Images
            </p>
            <p
              className="clickeable rounded-rect"
              onClick={() => goTo("/tools?selected=video")}
            >
              Video
            </p>
            <p
              className="clickeable rounded-rect"
              onClick={() => goTo("/whatsapp")}
            >
              WhatsApp
            </p>
          </>
        )}
      </div>
      <div>
        <h3
          className={`button ${openedSections.includes("training") ? "bg-hovered" : ""}`}
          onClick={() => handleSectionClick("training")}
        >
          Training
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
              Documents
            </p>

            <p
              className="clickeable rounded-rect"
              onClick={() =>
                setOpenedModals({ action: "add", name: "completions" })
              }
            >
              Completions
            </p>
            <p
              className="clickeable rounded-rect"
              onClick={() => setOpenedModals({ action: "add", name: "tags" })}
            >
              Tags
            </p>
          </>
        )}
      </div>
      <div className="sidebar__footer d-flex justify-between">
        <SvgButton text={user ? user.username : "You"} />
        <SvgButton svg={SVGS.controls} text="Settings" />
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
              top="0"
              opener={
                <SvgButton title="Conversation options" svg={SVGS.options} />
              }
            >
              <SvgButton
                size="big"
                svg={SVGS.trash}
                title="Delete conversation"
                text="Delete"
                confirmations={["Sure?"]}
                onClick={() => deleteConversationItem(conversation.id)}
                extraClass="bg-danger"
              />
              <SvgButton
                size="big"
                svg={SVGS.dumbell}
                title="Train on this conversation"
                text="Train"
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
      toast.error("Please select at least one agent");
    }

    const res = await generateTrainingCompletions({
      model_id: conversation.id,
      db_model: "conversation",
      agents: selectedAgents,
      completions_target_number: completionsTargetNumber,
    });
    toast.success("Training generation in queue...");
  };

  return (
    <Modal hide={hide}>
      <div className="d-flex flex-y gap-big">
        <h2 className="text-center">Generate completions</h2>
        <p>
          If you think the conversation <strong>{conversation.title}</strong> is
          relevant to your business, you can generate completions for it to add
          more context to your agents when answering similar conversations in
          the future.
        </p>
        <p>
          After generating completions, you can approve, edit or discard them.
        </p>
        <form onSubmit={onSubmit} action="">
          <label>
            Number of completions to generate
            <input
              className="input"
              type="number"
              defaultValue={30}
              onChange={(e) =>
                setCompletionsTargetNumber(parseInt(e.target.value))
              }
            />
          </label>
          <p>
            Select the agents that will retrain on this conversation. Keep in
            mind that each agent will generate its own completions based on its
            system prompt.
          </p>
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

export const Pill = ({
  children,
  extraClass = "",
  onClick = () => {},
}: {
  children: React.ReactNode;
  extraClass?: string;
  onClick?: () => void;
}) => {
  return (
    <span onClick={onClick} className={`pill ${extraClass}`}>
      {children}
    </span>
  );
};
