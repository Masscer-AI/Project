import { fetchUrlContent } from "../../modules/utils";
import React, { useState } from "react";
import { Modal } from "../Modal/Modal";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

type TResponseFormat = "text" | "json";
const allowedFormats = ["text", "json"];
export const WebsiteFetcher = () => {
  const { t } = useTranslation();
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [responseFormat, setResponseFormat] = useState<TResponseFormat>("text");
  const [content, setContent] = useState("");

  const handleFetch = async () => {
    try {
      setIsLoading(true);
      const content = await fetchUrlContent(url, responseFormat);
      console.log(content);
      toast.success("Content fetched");

      setContent(content);
    } catch (error) {
      toast.error("Error fetching content");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <Modal hide={() => setIsOpen(false)} visible={isOpen}>
        <h2>{t("website-content")}</h2>
        <pre>{JSON.stringify(content, null, 2)}</pre>
        <input
          className="input"
          placeholder={t("enter-website-url")}
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <select
          value={responseFormat}
          onChange={(e) => setResponseFormat(e.target.value as TResponseFormat)}
        >
          {allowedFormats.map((format) => (
            <option value={format}>{format}</option>
          ))}
        </select>
        <SvgButton
          onClick={handleFetch}
          svg={SVGS.webSearch}
          text={isLoading ? "Loading..." : t("fetch-website-content")}
        />
      </Modal>
      <button onClick={() => setIsOpen(!isOpen)}>Open</button>
    </div>
  );
};
