import React, { useRef, useState } from "react";
import { SVGS } from "../../assets/svgs";
import { v4 as uuidv4 } from "uuid";
import { useStore } from "../../modules/store";
import "./ChatInput.css";
import toast from "react-hot-toast";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import { SvgButton } from "../SvgButton/SvgButton";

interface ChatInputProps {
  handleSendMessage: () => void;
  handleKeyDown: (event, isWritingMode: boolean) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  handleSendMessage,
  handleKeyDown,
}) => {
  const [isWritingMode, setIsWritingMode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { input, setInput, attachments, addAttachment } = useStore((state) => ({
    input: state.input,
    setInput: state.setInput,
    attachments: state.chatState.attachments,
    addAttachment: state.addAttachment,
  }));

  const allowedImageTypes = [
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
  ];
  const allowedDocumentTypes = [
    "application/pdf",
    "text/plain",
    "text/html",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ];

  const handlePaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = event.clipboardData.items;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (allowedImageTypes.includes(item.type)) {
        const blob = item.getAsFile();
        const reader = new FileReader();

        reader.onload = (event) => {
          const target = event.target;
          if (!target) return;
          const result = target.result;
          if (!result) return;
          const id = uuidv4();

          console.log("PASTING SOMETHING IN THE INPUT");

          if (!blob) return;

          addAttachment({
            content: result as string,
            type: "image",
            name: id,
            file: blob,
          });
        };
        if (blob) reader.readAsDataURL(blob);
      }
    }
  };

  const addDocument = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (
        allowedImageTypes.includes(file.type) ||
        allowedDocumentTypes.includes(file.type)
      ) {
        const reader = new FileReader();
        reader.onload = (event) => {
          const target = event.target;
          if (!target) return;
          const result = target.result;
          if (!result) return;
          addAttachment({
            content: result as string,
            file: file,
            type: file.type,
            name: file.name,
          });
        };
        reader.readAsDataURL(file);
      } else {
        toast.error("File type not allowed 👀");
      }
    }
  };

  const openDocuments = () => {
    if (!fileInputRef || !fileInputRef.current) return;
    fileInputRef.current.click();
  };

  const toggleWritingMode = (e) => {
    console.log(e.target);

    console.log("Toggling writting mode");

    setIsWritingMode(!isWritingMode);
  };

  return (
    <div className="chat-input">
      <section className="attachments">
        {attachments.map(({ content, type, name, file }, index) => (
          <Thumbnail
          file={file}
            name={name}
            type={type}
            src={content}
            key={index}
            index={index}
          />
        ))}
      </section>
      <section>
        <textarea
          className={isWritingMode ? "big-size" : ""}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => handleKeyDown(e, isWritingMode)}
          onPaste={handlePaste}
          placeholder="Type your message..."
        />
        <div>
          {/* <button className="button" onClick={handleSendMessage}>{SVGS.send}</button> */}
          <SvgButton onClick={handleSendMessage} svg={SVGS.send} />
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={addDocument}
            style={{ display: "none" }}
            id="fileInput"
            accept=".png,.jpeg,.jpg,.gif,.webp,.pdf,.txt,.html,.doc,.docx"
          />
          <label htmlFor="fileInput">
            {/* <button onClick={openDocuments}>{SVGS.addDocument}</button> */}
            <SvgButton onClick={openDocuments} svg={SVGS.addDocument} />
          </label>
          <SvgButton
            extraClass={isWritingMode ? "active" : ""}
            onClick={toggleWritingMode}
            svg={SVGS.writePen}
          />
        </div>
      </section>
    </div>
  );
};
