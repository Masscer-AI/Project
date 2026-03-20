import React from "react";
import { TConversation } from "../types";

interface ConversationListProps {
  conversations: TConversation[];
  onSelect: (conversation: TConversation) => void;
  onNewConversation: () => void;
  isLoading: boolean;
}

const formatDate = (iso: string) => {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return date.toLocaleDateString([], { weekday: "long" });
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
};

const ConversationList: React.FC<ConversationListProps> = ({
  conversations,
  onSelect,
  onNewConversation,
  isLoading,
}) => {
  return (
    <div className="widget-conv-list">
      <div className="widget-conv-list-header">
        <span className="widget-conv-list-title">Previous chats</span>
        <button
          className="widget-conv-new-btn"
          onClick={onNewConversation}
          disabled={isLoading}
        >
          + New chat
        </button>
      </div>
      <div className="widget-conv-list-items">
        {isLoading ? (
          <div className="widget-conv-list-empty">Loading...</div>
        ) : conversations.length === 0 ? (
          <div className="widget-conv-list-empty">No previous conversations</div>
        ) : (
          conversations.map((conv) => {
            const preview = (conv as any).last_message_preview as string | null;
            return (
              <button
                key={conv.id}
                className="widget-conv-item"
                onClick={() => onSelect(conv)}
              >
                <div className="widget-conv-item-meta">
                  <span className="widget-conv-item-date">
                    {formatDate(conv.updated_at ?? conv.created_at)}
                  </span>
                  <span className="widget-conv-item-count">
                    {conv.number_of_messages}{" "}
                    {conv.number_of_messages === 1 ? "message" : "messages"}
                  </span>
                </div>
                <div className="widget-conv-item-preview">{preview || "No preview available"}</div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ConversationList;
