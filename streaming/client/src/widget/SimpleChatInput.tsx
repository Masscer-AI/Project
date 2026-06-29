import React, { useState, useRef, KeyboardEvent } from "react";
import { PoweredByMasscer } from "../components/PoweredByMasscer/PoweredByMasscer";
import "./SimpleChatInput.css";

interface SimpleChatInputProps {
  onSendMessage: (message: string, files: File[]) => Promise<boolean>;
  disabled?: boolean;
  allowAttachments?: boolean;
}

export const SimpleChatInput: React.FC<SimpleChatInputProps> = ({
  onSendMessage,
  disabled = false,
  allowAttachments = false,
}) => {
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = async () => {
    const trimmed = input.trim();
    if ((!trimmed && pendingFiles.length === 0) || isSending || disabled) return;

    setIsSending(true);
    setInput("");
    const filesToSend = [...pendingFiles];
    setPendingFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";

    try {
      await onSendMessage(trimmed, filesToSend);
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

  const onPickFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    if (!list?.length) return;
    setPendingFiles((prev) => [...prev, ...Array.from(list)]);
  };

  const removePendingFile = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="simple-chat-input-wrapper">
      {allowAttachments && pendingFiles.length > 0 && (
        <div className="simple-chat-pending-files">
          {pendingFiles.map((f, i) => (
            <span key={`${f.name}-${i}`} className="simple-chat-pending-chip">
              <span className="simple-chat-pending-name">{f.name}</span>
              <button
                type="button"
                className="simple-chat-pending-remove"
                onClick={() => removePendingFile(i)}
                aria-label="Remove file"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="simple-chat-input-container">
        {allowAttachments && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="simple-chat-file-input"
              aria-hidden
              tabIndex={-1}
              accept=".png,.jpeg,.jpg,.gif,.webp,.pdf,.txt,.html,.doc,.docx,.xlsx"
              onChange={onPickFiles}
            />
            <button
              type="button"
              className="simple-chat-attach-button"
              disabled={disabled || isSending}
              onClick={() => fileInputRef.current?.click()}
              aria-label="Attach files"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
          </>
        )}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.currentTarget.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe tu mensaje..."
          disabled={disabled || isSending}
          className="simple-chat-input"
        />
        <button
          onClick={handleSend}
          disabled={
            disabled ||
            isSending ||
            (input.trim() === "" && pendingFiles.length === 0)
          }
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
      <PoweredByMasscer className="simple-chat-disclaimer" />
    </div>
  );
};
