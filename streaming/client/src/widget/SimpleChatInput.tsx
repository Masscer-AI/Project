import React, { useState, KeyboardEvent } from "react";
import "./SimpleChatInput.css";

interface SimpleChatInputProps {
  onSendMessage: (message: string) => Promise<boolean>;
  disabled?: boolean;
}

export const SimpleChatInput: React.FC<SimpleChatInputProps> = ({
  onSendMessage,
  disabled = false,
}) => {
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);

  const handleSend = async () => {
    if (input.trim() === "" || isSending || disabled) return;

    setIsSending(true);
    const message = input.trim();
    setInput("");

    try {
      await onSendMessage(message);
    } catch (error) {
      console.error("Error sending message:", error);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="simple-chat-input-container">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Escribe tu mensaje..."
        disabled={disabled || isSending}
        className="simple-chat-input"
      />
      <button
        onClick={handleSend}
        disabled={disabled || isSending || input.trim() === ""}
        className="simple-chat-send-button"
        aria-label="Enviar mensaje"
      >
        {isSending ? (
          <div className="simple-chat-spinner"></div>
        ) : (
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        )}
      </button>
    </div>
  );
};

