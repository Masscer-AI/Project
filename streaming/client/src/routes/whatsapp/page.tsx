import React, { useEffect, useState } from "react";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { ChatHeader } from "../../components/ChatHeader/ChatHeader";
import { Card } from "../../components/Card/Card";
import "./page.css";
import { useLoaderData } from "react-router-dom";
import { Modal } from "../../components/Modal/Modal";
import {
  getWhatsappConversations,
  getWhatsappConversationMessages,
  sendMessageToConversation,
  updateWhatsappNumber,
} from "../../modules/apiCalls";
import MarkdownRenderer from "../../components/MarkdownRenderer/MarkdownRenderer";
import { AgentSelector } from "../../components/AgentSelector/AgentSelector";
import toast, { Toaster } from "react-hot-toast";
export default function Whatsapp() {
  const { isSidebarOpened } = useStore((s) => ({
    isSidebarOpened: s.chatState.isSidebarOpened,
  }));

  const { numbers } = useLoaderData() as { numbers: any[] };

  console.log(numbers);

  return (
    <main className="whatsapp-page">
      <div className="d-flex">
        {isSidebarOpened && <Sidebar />}
        <div className="chat-max-width ">
          <ChatHeader onTitleEdit={() => {}} title="" />
          <div className="padding-big">
            <h1>Whatsapp</h1>
            <p>
              Masscer AI let's you use AI Agents inside Whatsapp, in this way
              you can boost your customer services and collect information about
              your contacts.
            </p>
            <SvgButton text="Connect to Whatsapp" svg={"✅"} />
            <p>These are your WhatsApp numbers</p>
            <div>
              {numbers.map((number) => (
                <WhatsAppNumber key={number.id} {...number} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

const WhatsAppNumber = ({
  number,
  agent,
  conversations_count,
  name,
}: {
  number: string;
  agent: any;
  conversations_count: number;
  name: string;
}) => {
  const [isModalVisible, setIsModalVisible] = useState(false);

  const [conversations, setConversations] = useState<any[]>([]);
  const [nameInput, setNameInput] = useState(name ? name : "");

  const showConversations = () => {
    setIsModalVisible(true);
  };

  const hideConversations = () => {
    setIsModalVisible(false);
  };

  useEffect(() => {
    getWhatsappConversations().then((res) => {
      // @ts-ignore
      setConversations(res);
    });
  }, []);

  const changeAgent = (slug: string) => {
    updateWhatsappNumber(number, { slug }).then((res) => {
      toast.success("Agent changed");
    });
  };

  const updateName = () => {
    updateWhatsappNumber(number, { name: nameInput }).then((res) => {
      toast.success("Name updated");
    });
  };

  return (
    <>
      <Card onClick={showConversations}>
        <h2 className="text-center">{name}</h2>
        <h3 className="text-center">📞{number}</h3>
        <div className="d-flex justify-center gap-medium">
          <span className="text-center">🧠 {agent.name}</span>
          <span className="text-center">💬 {conversations_count}</span>
        </div>
      </Card>
      {isModalVisible && (
        <Modal hide={hideConversations} visible={isModalVisible}>
          <h2 className="text-center">Conversations</h2>
          <section className="d-flex flex-y gap-small justify-center align-center">
            <p>Number: {number}</p>
            <p className="d-flex align-center gap-small wrap-wrap">
              <span>Name:</span>
              <input
                className="input"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                type="text"
              />

              <SvgButton onClick={updateName} text="Update name" svg={"💾"} />
            </p>
            <div className="d-flex align-center gap-small wrap-wrap">
              <p>Change the agent for this number</p>
              <AgentSelector
                onSelectAgent={changeAgent}
                selectedSlug={agent.slug}
              />
            </div>
          </section>
          <div className="d-flex gap-medium wrap-wrap my-medium">
            {conversations.map((conversation) => (
              <ConversationComponent key={conversation.id} {...conversation} />
            ))}
          </div>
        </Modal>
      )}
    </>
  );
};

const ConversationComponent = ({
  title,
  user_number,
  id,
  summary,
  sentiment,
}: {
  title: string;
  user_number: string;
  id: string;
  summary: string;
  sentiment: string;
}) => {
  const [messages, setMessages] = useState<any[]>([]);
  const [showMessages, setShowMessages] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const [messageInput, setMessageInput] = useState("");
  const getMessages = () => {
    getWhatsappConversationMessages(id).then((res) => {
      console.log(res);
      // @ts-ignore
      setMessages(res.messages);
      setShowMessages(true);
    });
  };

  const sendMessage = () => {
    if (messageInput.trim() === "") return;
    sendMessageToConversation(id, messageInput).then((res) => {
      setMessageInput("");
    });
  };

  return (
    <>
      <Card onClick={getMessages}>
        <h3>{title}</h3>
        <p>
          {user_number} <span>{sentiment}</span>
        </p>
      </Card>
      <Modal hide={() => setShowMessages(false)} visible={showMessages}>
        <div className="whatsapp-header">
          <h3>{title ? title : "No title"}</h3>
          <p>
            {summary ? (
              showMore ? (
                summary
              ) : (
                summary.slice(0, 80) + "..."
              )
            ) : (
              <span className="text-center">No summary</span>
            )}
            <button className="button" onClick={() => setShowMore(!showMore)}>
              {showMore ? "Ocultar" : "Leer más →"}
            </button>
          </p>
        </div>
        <div className="whatsapp-messages">
          {messages &&
            messages.map((message) => (
              <WhatsAppMessage key={message.id} {...message} />
            ))}
        </div>
        <div className="d-flex gap-small justify-center align-center padding-medium">
          <textarea
            onChange={(e) => setMessageInput(e.target.value)}
            value={messageInput}
            placeholder="Escribe un mensaje"
            className="button w-100"
          />
          <SvgButton onClick={() => sendMessage()} text="Send" svg={"💬"} />
        </div>
      </Modal>
    </>
  );
};

const WhatsAppMessage = ({
  content,
  message_type,
  created_at,
  reaction,
}: {
  content: string;
  message_type: string;
  created_at: string;
  reaction: string;
}) => {
  // Create a Date object from the created_at string
  const date = new Date(created_at);

  // Format the date to a more readable format
  const formattedDate = date.toLocaleString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });

  return (
    <div
      className={`text-center d-flex flex-y message ${message_type.toLowerCase()}`}
    >
      <div className=" text-left message-text">
        <MarkdownRenderer markdown={content} />
        {reaction && <span className="reaction">{reaction} ✔️✔️</span>}
      </div>
      <div className="d-flex align-center padding-medium">
        <p className="text-small">{formattedDate}</p>
      </div>
    </div>
  );
};
