import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { fetchUrlContent } from "../../modules/apiCalls";
import { useStore } from "../../modules/store";
import { TSpecifiedUrl } from "../../modules/storeTypes";

type FetchedUrl = {
  url: string;
  content: string;
  status: "pending" | "success" | "error";
  errorMessage?: string;
};

export const WebsiteFetcher = ({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) => {
  const { t } = useTranslation();
  const { setSpecifiedUrls, chatState } = useStore((state) => ({
    setSpecifiedUrls: state.setSpecifiedUrls,
    chatState: state.chatState,
  }));

  const [urlInput, setUrlInput] = useState("");
  const [fetchedUrls, setFetchedUrls] = useState<FetchedUrl[]>([]);

  // Load existing URLs from store when modal opens
  useEffect(() => {
    if (isOpen) {
      const existing = chatState.specifiedUrls || [];
      if (existing.length > 0) {
        setFetchedUrls(
          existing.map((item) => ({
            url: item.url,
            content: item.content,
            status: item.content ? "success" : "pending",
          }))
        );
      }
    } else {
      // Reset local state when modal closes
      setFetchedUrls([]);
      setUrlInput("");
    }
  }, [isOpen, chatState.specifiedUrls]);

  const handleAddUrl = () => {
    if (!urlInput.trim()) {
      toast.error(t("please-enter-a-valid-url") || "Please enter a valid URL");
      return;
    }

    // Basic URL validation
    try {
      new URL(urlInput.trim());
    } catch {
      toast.error(t("invalid-url-format") || "Invalid URL format");
      return;
    }

    const newUrl = urlInput.trim();
    if (fetchedUrls.some((f) => f.url === newUrl)) {
      toast.error(t("url-already-added") || "URL already added");
      return;
    }

    const newIndex = fetchedUrls.length;
    setFetchedUrls((prev) => [
      ...prev,
      { url: newUrl, content: "", status: "pending" },
    ]);
    setUrlInput("");
    handleFetchUrl(newUrl, newIndex);
  };

  const handleFetchUrl = async (url: string, index: number) => {
    setFetchedUrls((prev) =>
      prev.map((item, i) =>
        i === index
          ? { ...item, status: "pending" as const, errorMessage: undefined }
          : item
      )
    );

    try {
      const response = await fetchUrlContent(url);
      const content = response?.content ?? "";

      if (content.trim().length > 0) {
        setFetchedUrls((prev) =>
          prev.map((item, i) =>
            i === index
              ? {
                  ...item,
                  content,
                  status: "success" as const,
                  errorMessage: undefined,
                }
              : item
          )
        );
        toast.success(
          t("content-fetched-successfully") || "Content fetched successfully"
        );
      } else {
        setFetchedUrls((prev) =>
          prev.map((item, i) =>
            i === index
              ? {
                  ...item,
                  status: "error" as const,
                  errorMessage: t("error-fetching-content") || "Error fetching content",
                }
              : item
          )
        );
        toast.error(t("error-fetching-content") || "Error fetching content");
      }
    } catch (error: any) {
      const message =
        error?.response?.data?.error ||
        error?.message ||
        t("error-fetching-content") ||
        "Error fetching content";

      setFetchedUrls((prev) =>
        prev.map((item, i) =>
          i === index
            ? {
                ...item,
                status: "error" as const,
                errorMessage: message,
              }
            : item
        )
      );
      toast.error(message);
    }
  };

  const handleRemoveUrl = (index: number) => {
    setFetchedUrls((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUseInMessage = () => {
    const successfulUrls = fetchedUrls
      .filter((f) => f.status === "success" && f.content.trim().length > 0)
      .map<TSpecifiedUrl>((f) => ({ url: f.url, content: f.content }));

    if (successfulUrls.length === 0) {
      toast.error(
        t("no-urls-fetched-successfully") || "No URLs fetched successfully"
      );
      return;
    }

    setSpecifiedUrls(successfulUrls);
    toast.success(
      t("urls-added-to-message") || `${successfulUrls.length} URL(s) added to message`
    );
    onClose();
  };

  const statusLabels: Record<FetchedUrl["status"], string> = {
    pending: t("pending") || "Pending",
    success: t("fetched") || "Fetched",
    error: t("error") || "Error",
  };

  return (
    <Modal
      hide={onClose}
      visible={isOpen}
      header={<h2 className="text-center">{t("website-content-fetcher")}</h2>}
    >
      <div className="flex-y gap-medium">
        <div className="flex-x gap-small">
          <input
            className="input flex-1"
            placeholder={t("enter-website-url") || "Enter website URL"}
            type="text"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleAddUrl();
              }
            }}
          />
          <SvgButton
            onClick={handleAddUrl}
            svg={SVGS.plus}
            text={t("add-url") || "Add URL"}
            extraClass="border-active"
          />
        </div>

        {fetchedUrls.length > 0 && (
          <div className="flex-y gap-small">
            <h4>{t("added-urls") || "Added URLs"}</h4>

            <div className="flex-y gap-small url-list">
              {fetchedUrls.map((fetchedUrl, index) => (
                <div key={index} className="card website-fetcher-card">
                  <div className="flex-x gap-small align-start justify-between">
                    <div className="flex-y gap-small flex-1">
                      <div className="flex-x gap-small align-center">
                        <p className="cut-text-to-line flex-1" title={fetchedUrl.url}>
                          {fetchedUrl.url}
                        </p>
                        {fetchedUrl.status === "pending" && (
                          <div className="spinner-small"></div>
                        )}
                        {fetchedUrl.status !== "pending" && (
                          <span className={`status-badge status-${fetchedUrl.status}`}>
                            {statusLabels[fetchedUrl.status]}
                          </span>
                        )}
                      </div>

                      {fetchedUrl.status === "success" && fetchedUrl.content && (
                        <pre className="website-fetcher-preview">
                          {fetchedUrl.content.substring(0, 300)}
                          {fetchedUrl.content.length > 300 ? "..." : ""}
                        </pre>
                      )}

                      {fetchedUrl.status === "error" && fetchedUrl.errorMessage && (
                        <p className="text-error text-mini">{fetchedUrl.errorMessage}</p>
                      )}
                    </div>

                    <SvgButton
                      onClick={() => handleRemoveUrl(index)}
                      svg={SVGS.trash}
                      extraClass="border-active"
                      title={t("remove") || "Remove"}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex-x gap-small justify-end">
          <SvgButton
            onClick={onClose}
            text={t("cancel") || "Cancel"}
            extraClass="border-active"
          />
          {fetchedUrls.length > 0 && (
            <SvgButton
              onClick={handleUseInMessage}
              svg={SVGS.send}
              text={t("use-in-message") || "Use in Message"}
              extraClass="bg-active svg-white"
            />
          )}
        </div>
      </div>
    </Modal>
  );
};
