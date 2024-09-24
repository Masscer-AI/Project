import React, { useEffect, useState } from "react";
import axios from "axios";
import "./Sidebar.css";
import { SVGS } from "../../assets/svgs";
import { API_URL } from "../../modules/constants";
import { useStore } from "../../modules/store";
import { useSearchParams } from "react-router-dom";
// import { useNavigate } from "react-router-dom";

interface TConversation {
  id: string;
  user_id: number;
  number_of_messages: number;
  title: undefined | string;
}

export const Sidebar: React.FC = () => {
  const { toggleSidebar, setConversation } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    setConversation: state.setConversation,
  }));

  // const navigate = useNavigate();
  const [history, setHistory] = useState<TConversation[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();

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
      console.log(conversations);

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
  };

  return (
    <div className="sidebar">
      <div className="sidebar__header">
        <button className="button" onClick={handleNewChat}>
          New chat
        </button>
        <button className="button" onClick={toggleSidebar}>
          {SVGS.burger}
        </button>
      </div>
      <div className="sidebar__history">
        {history.map((conversation) => (
          <ConversationComponent
            key={conversation.id}
            conversation={conversation}
          />
        ))}
      </div>
      <div className="sidebar__footer">Some user</div>
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

  const handleClick = (e) => {
    e.preventDefault();
    setConversation(conversation.id);
    toggleSidebar();
    const queryParams = {
      conversation: conversation.id,
    };
    setSearchParams(queryParams);
    console.log(searchParams);
  };

  return (
    <>
      {conversation.number_of_messages > 0 ? (
        <div className="conversation" onClick={handleClick}>
          <p>{conversation.title || conversation.id}</p>
        </div>
      ) : null}
    </>
  );
};
