import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { fetchUrlContent } from "../../modules/apiCalls";
import { Textarea } from "../SimpleForm/Textarea";

const extractTextFromHTML = (html: string) => {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, "text/html");
  return doc.body.innerText;
};

export const WebsiteFetcher = () => {
  const { t } = useTranslation();
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [content, setContent] = useState("");
  const [wordCount, setWordCount] = useState(0);

  const handleFetch = async () => {
    try {
      setIsLoading(true);
      const response = await fetchUrlContent(url);

      console.log(response);
      toast.success("Content fetched");
      if (response.status_code === 200) {
        if (response.content_type.includes("text/html")) {
          const text = extractTextFromHTML(response.content);
          setContent(text);
        } else {
          setContent(String(response.content));
        }
      } else {
        toast.error(t("error-fetching-content"));
        setContent("");
      }
    } catch (error) {
      toast.error(t("error-fetching-content"));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setWordCount(content.split(" ").length);
  }, [content]);

  return (
    <div>
      <Modal
        hide={() => setIsOpen(false)}
        visible={isOpen}
        header={<h2 className="text-center">{t("website-content-fetcher")}</h2>}
      >
        <div className="flex-x gap-small">
          <input
            className="input"
            placeholder={t("enter-website-url")}
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />

          <SvgButton
            onClick={handleFetch}
            svg={SVGS.webSearch}
            text={isLoading ? "Loading..." : t("fetch-website-content")}
          />
        </div>
        <Textarea
          extraClass="mt-big"
          defaultValue={content}
          onChange={(newValue) => setContent(newValue)}
          label={t("choose-relevant-content")}
        />
      </Modal>
      <button onClick={() => setIsOpen(!isOpen)}>Open</button>
    </div>
  );
};
