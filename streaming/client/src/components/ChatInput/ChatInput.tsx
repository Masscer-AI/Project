import React, { useState } from "react";
import { SVGS } from "../../assets/svgs";
import { v4 as uuidv4 } from "uuid";
import { useStore } from "../../modules/store";
import "./ChatInput.css";
// import { useSearchParams } from "react-router-dom";
interface ChatInputProps {
  handleSendMessage: () => void;
  handleKeyDown: (event) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  handleSendMessage,
  handleKeyDown,
}) => {
  // const [searchParams, setSearchParams] = useSearchParams();
  const { input, setInput } = useStore();
  const [attachments, setAttachments] = useState<{ [key: string]: string }>({});

  // useEffect(() => {
  //   console.log(searchParams);

  //   // const url = new URL(window.location.href);
  //   // url.searchParams.set("prompt", input);
  //   // window.history.pushState({}, "", url.toString());
  //   const params = {
  //     prompt: input,
  //   };
  //   setSearchParams(params);
  // }, [input, searchParams, setSearchParams]);

  const handlePaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    console.log("User trying to paste");

    const items = event.clipboardData.items;
    console.log("items", items);

    for (let i = 0; i < items.length; i++) {
      const item = items[i];

      if (item.type.indexOf("image") === 0) {
        const blob = item.getAsFile();
        const reader = new FileReader();
        reader.onload = (event) => {
          const target = event.target;
          if (!target) return;

          const result = event.target.result;

          if (!result) return;
          const id = uuidv4();
          setAttachments((prev) => ({ ...prev, [id]: result as string }));
        };
        if (blob) {
          reader.readAsDataURL(blob);
        }
      } else if (item.type === "text/plain") {
        item.getAsString((textToAdd) => {
          console.log("About to add text", textToAdd);
        });
      }
    }
  };

  return (
    <div className="chat-input">
      <section className="attachments">
        {Object.entries(attachments).map(([key, src]) => (
          <Thumbnail src={src} key={key} name={key} />
        ))}
      </section>
      <section>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="Type your message..."
        />
        <button onClick={handleSendMessage}>{SVGS.send}</button>
      </section>
    </div>
  );
};

const Thumbnail = ({ src, name }) => {
  return (
    <div className="thumbnail">
      <img key={name} src={src} alt={`attachment-${name}`} />
    </div>
  );
};
