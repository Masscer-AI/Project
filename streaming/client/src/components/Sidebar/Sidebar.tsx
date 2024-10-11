import React, { useEffect, useState } from "react";
import axios from "axios";
import "./Sidebar.css";
import { SVGS } from "../../assets/svgs";
import { API_URL } from "../../modules/constants";
import { useStore } from "../../modules/store";
import { Link, useSearchParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { SvgButton } from "../SvgButton/SvgButton";

interface TConversation {
  id: string;
  user_id: number;
  number_of_messages: number;
  title: undefined | string;
}

export const Sidebar: React.FC = () => {
  const { toggleSidebar, setConversation, user } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    setConversation: state.setConversation,
    user: state.user,
  }));

  const [history, setHistory] = useState<TConversation[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
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
      const requestUrl = API_URL + "/v1/messaging/conversations";
      const res = await axios.get<TConversation[]>(requestUrl, {
        headers: {
          Authorization: `Token ${token}`,
        },
      });

      const conversations = res.data;
      setHistory(conversations);
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

  return (
    <div className="sidebar">
      <div className="sidebar__header">
        <button className=" clickeable button" onClick={handleNewChat}>
          New chat
        </button>
        <SvgButton onClick={toggleSidebar} svg={SVGS.burger} />
      </div>
      <details className="sidebar__history">
        <summary>Conversations</summary>
        {history.map((conversation) => (
          <ConversationComponent
            key={conversation.id}
            conversation={conversation}
          />
        ))}
      </details>
      <details>
        <summary>Tools</summary>
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
      </details>
      <details>
        <summary>Training</summary>
        <p
          className="clickeable rounded-rect"
          // onClick={() => goTo("/tools?selected=audio")}
        >
          Documents
        </p>
        <p
          className="clickeable rounded-rect"
          // onClick={() => goTo("/tools?selected=images")}
        >
          Questions
        </p>
        <p
          className="clickeable rounded-rect"
          // onClick={() => goTo("/tools?selected=video")}
        >
          Tags
        </p>
      </details>
      <div className="sidebar__footer">{user ? user.username : "You"}</div>
    </div>
  );
};

const ConversationComponent = ({
  conversation,
}: {
  conversation: TConversation;
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { setConversation, toggleSidebar } = useStore((state) => ({
    setConversation: state.setConversation,
    toggleSidebar: state.toggleSidebar,
  }));
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
        <div
          className="conversation clickeable rounded-rect"
          onClick={handleClick}
        >
          <p>{(conversation.title || conversation.id).slice(0, 30)}</p>
        </div>
      ) : null}
    </>
  );
};
