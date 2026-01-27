import React, { useEffect, useRef, useState } from "react";
import { Modal } from "../Modal/Modal";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { SvgButton } from "../SvgButton/SvgButton";
import { Icon } from "../Icon/Icon";
import {
  createWebPage,
  deleteWebPage,
  fetchUrlContent,
  getWebPages,
} from "../../modules/apiCalls";
import { useStore } from "../../modules/store";
import { TSpecifiedUrl } from "../../modules/storeTypes";
import { TWebPage } from "../../types";

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
  const [savedPages, setSavedPages] = useState<TWebPage[]>([]);
  const [isLoadingSaved, setIsLoadingSaved] = useState(false);
  const [selectedUrls, setSelectedUrls] = useState<string[]>([]);
  const [contentModal, setContentModal] = useState<{
    isOpen: boolean;
    url: string;
    content: string;
  }>({ isOpen: false, url: "", content: "" });
  const hasInitializedRef = useRef(false);

  // Load existing URLs from store when modal opens
  useEffect(() => {
    if (!isOpen) {
      // Reset local state when modal closes
      setFetchedUrls([]);
      setUrlInput("");
      setSelectedUrls([]);
      hasInitializedRef.current = false;
      return;
    }

    if (hasInitializedRef.current) {
      return;
    }

    const existing = chatState.specifiedUrls || [];
    if (existing.length > 0) {
      setFetchedUrls(
        existing.map((item) => ({
          url: item.url,
          content: item.content,
          status: item.content ? "success" : "pending",
        }))
      );
      setSelectedUrls(existing.map((item) => item.url));
    }
    loadSavedPages();
    hasInitializedRef.current = true;
  }, [isOpen]);

  const sortSavedPages = (pages: TWebPage[]) => {
    return [...pages].sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) {
        return a.is_pinned ? -1 : 1;
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  };

  useEffect(() => {
    const selected = fetchedUrls
      .filter(
        (f) =>
          f.status === "success" &&
          f.content.trim().length > 0 &&
          selectedUrls.includes(f.url)
      )
      .map<TSpecifiedUrl>((f) => ({ url: f.url, content: f.content }));
    setSpecifiedUrls(selected);
  }, [fetchedUrls, selectedUrls, setSpecifiedUrls]);

  const loadSavedPages = async () => {
    if (isLoadingSaved) {
      return;
    }
    setIsLoadingSaved(true);
    try {
      const pages = await getWebPages();
      setSavedPages(sortSavedPages(pages || []));
    } catch (error) {
      console.error("Error loading saved pages:", error);
      toast.error(t("error-loading-saved-pages") || "Error loading saved pages");
    } finally {
      setIsLoadingSaved(false);
    }
  };

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

  const ensureFetchedUrl = (url: string) => {
    const existingIndex = fetchedUrls.findIndex((item) => item.url === url);
    if (existingIndex !== -1) {
      return existingIndex;
    }
    const nextIndex = fetchedUrls.length;
    setFetchedUrls((prev) => [
      ...prev,
      { url, content: "", status: "pending" },
    ]);
    handleFetchUrl(url, nextIndex);
    return nextIndex;
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
        setSelectedUrls((prev) =>
          prev.includes(url) ? prev : [...prev, url]
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


  const handleSavePage = async (url: string, title?: string) => {
    try {
      const saved = await createWebPage({ url, title });
      setSavedPages((prev) => {
        const exists = prev.some((p) => p.id === saved.id);
        const next = exists
          ? prev.map((p) => (p.id === saved.id ? saved : p))
          : [...prev, saved];
        return sortSavedPages(next);
      });
      toast.success(t("saved-page-successfully") || "Page saved successfully");
    } catch (error: any) {
      const message =
        error?.response?.data?.error ||
        error?.message ||
        t("error-saving-page") ||
        "Error saving page";
      toast.error(message);
    }
  };

  const handleDeleteSaved = async (page: TWebPage) => {
    try {
      await deleteWebPage(page.id);
      setSavedPages((prev) => prev.filter((p) => p.id !== page.id));
      toast.success(t("page-removed") || "Page removed");
    } catch (error) {
      toast.error(t("error-removing-page") || "Error removing page");
    }
  };

  const handleRemoveUrl = (index: number) => {
    const urlToRemove = fetchedUrls[index]?.url;
    setFetchedUrls((prev) => prev.filter((_, i) => i !== index));
    if (urlToRemove) {
      setSelectedUrls((prev) => prev.filter((url) => url !== urlToRemove));
    }
  };

  const handleToggleSelected = (url: string) => {
    setSelectedUrls((prev) => {
      if (prev.includes(url)) {
        return prev.filter((u) => u !== url);
      }
      ensureFetchedUrl(url);
      return [...prev, url];
    });
  };

  const statusLabels: Record<FetchedUrl["status"], string> = {
    pending: t("pending") || "Pending",
    success: t("fetched") || "Fetched",
    error: t("error") || "Error",
  };

  const openContentModal = (url: string, content: string) => {
    setContentModal({ isOpen: true, url, content });
  };

  return (
    <Modal
      hide={onClose}
      visible={isOpen}
      header={<h2 className="text-center">{t("website-content-fetcher")}</h2>}
    >
      <div className="flex-y gap-medium">
        <div className="flex-x gap-small website-fetcher-row">
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
            svg={<Icon name="Plus" />}
            extraClass="border-active"
            title={t("add-url") || "Add URL"}
          />
        </div>

        <div className="flex-y gap-small website-fetcher-section">
          {isLoadingSaved && (
            <p className="text-mini">{t("loading") || "Loading..."}</p>
          )}
          {!isLoadingSaved && savedPages.length === 0 && (
            <p className="text-mini text-secondary">
              {t("no-saved-pages-yet") || "No saved pages yet"}
            </p>
          )}
          {savedPages.length > 0 && (
            <div className="flex-y gap-small url-list">
              {savedPages.map((page) => {
                const fetched = fetchedUrls.find((f) => f.url === page.url);
                return (
                  <div key={page.id} className="card website-fetcher-card">
                    <div className="flex-y gap-small website-fetcher-row">
                      <p
                        className="cut-text-to-line flex-1 website-fetcher-url"
                        title={page.url}
                      >
                        {page.title ? `${page.title} - ${page.url}` : page.url}
                      </p>
                      <div className="flex-x gap-small website-fetcher-buttons">
                        <SvgButton
                          onClick={() => handleToggleSelected(page.url)}
                          svg={<Icon name="Globe" />}
                          extraClass={`border-active ${
                            selectedUrls.includes(page.url)
                              ? "bg-active svg-white"
                              : ""
                          }`}
                          title={
                            selectedUrls.includes(page.url)
                              ? t("unselect") || "Unselect"
                              : t("select") || "Select"
                          }
                          text={
                            selectedUrls.includes(page.url)
                              ? t("selected") || "Selected"
                              : t("select") || "Select"
                          }
                        />
                        {fetched?.status === "success" && fetched.content && (
                          <SvgButton
                            onClick={() => openContentModal(page.url, fetched.content)}
                            svg={<Icon name="Eye" />}
                            extraClass="border-active"
                            title={t("view") || "View"}
                            text={t("view") || "View"}
                          />
                        )}
                        <SvgButton
                          onClick={() => handleDeleteSaved(page)}
                          svg={<Icon name="Trash" />}
                          extraClass="border-active"
                          title={t("remove") || "Remove"}
                        />
                      </div>
                    </div>
                    {fetched?.status === "error" && fetched.errorMessage && (
                      <p className="text-error text-mini">{fetched.errorMessage}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {fetchedUrls.filter((f) => !savedPages.some((p) => p.url === f.url))
          .length > 0 && (
          <div className="flex-y gap-small website-fetcher-section">
            <div className="flex-y gap-small url-list">
              {fetchedUrls
                .filter((f) => !savedPages.some((p) => p.url === f.url))
                .map((fetchedUrl, index) => (
                <div key={index} className="card website-fetcher-card">
                  <div className="flex-y gap-small website-fetcher-row">
                    <div className="flex-x gap-small align-center website-fetcher-row">
                      <p
                        className="cut-text-to-line flex-1 website-fetcher-url"
                        title={fetchedUrl.url}
                      >
                        {fetchedUrl.url}
                      </p>
                      {fetchedUrl.status === "pending" && (
                        <div className="spinner-small"></div>
                      )}
                      {fetchedUrl.status === "error" && (
                        <span className={`status-badge status-${fetchedUrl.status}`}>
                          {statusLabels[fetchedUrl.status]}
                        </span>
                      )}
                    </div>

                    {fetchedUrl.status === "error" && fetchedUrl.errorMessage && (
                      <p className="text-error text-mini">{fetchedUrl.errorMessage}</p>
                    )}

                    <div className="flex-x gap-small website-fetcher-buttons">
                      <SvgButton
                        onClick={() => handleToggleSelected(fetchedUrl.url)}
                        svg={<Icon name="Globe" />}
                        extraClass={`border-active ${
                          selectedUrls.includes(fetchedUrl.url)
                            ? "bg-active svg-white"
                            : ""
                        }`}
                        title={
                          selectedUrls.includes(fetchedUrl.url)
                            ? t("unselect") || "Unselect"
                            : t("select") || "Select"
                        }
                        text={
                          selectedUrls.includes(fetchedUrl.url)
                            ? t("selected") || "Selected"
                            : t("select") || "Select"
                        }
                      />
                      {fetchedUrl.status === "success" && fetchedUrl.content && (
                        <SvgButton
                          onClick={() =>
                            openContentModal(fetchedUrl.url, fetchedUrl.content)
                          }
                          svg={<Icon name="Eye" />}
                          extraClass="border-active"
                          title={t("view") || "View"}
                          text={t("view") || "View"}
                        />
                      )}
                      <SvgButton
                        onClick={() => handleRemoveUrl(index)}
                        svg={<Icon name="Trash" />}
                        extraClass="border-active"
                        title={t("remove") || "Remove"}
                      />
                      {fetchedUrl.status === "success" &&
                        fetchedUrl.content &&
                        !savedPages.some((p) => p.url === fetchedUrl.url) && (
                          <SvgButton
                            onClick={() => handleSavePage(fetchedUrl.url)}
                            svg={<Icon name="Save" />}
                            extraClass="border-active"
                            title={t("save") || "Save"}
                          />
                        )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <Modal
          hide={() => setContentModal({ isOpen: false, url: "", content: "" })}
          visible={contentModal.isOpen}
          header={<h3 className="text-center">{t("inspect-content") || "Inspect content"}</h3>}
        >
          <div className="flex-y gap-small">
            <p className="text-mini cut-text-to-line" title={contentModal.url}>
              {contentModal.url}
            </p>
            <pre className="website-fetcher-preview">
              {contentModal.content}
            </pre>
          </div>
        </Modal>
      </div>
    </Modal>
  );
};
