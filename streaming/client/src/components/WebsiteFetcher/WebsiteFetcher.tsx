import React, { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import {
  createWebPage,
  deleteWebPage,
  fetchUrlContent,
  getWebPages,
} from "../../modules/apiCalls";
import { useStore } from "../../modules/store";
import { TSpecifiedUrl } from "../../modules/storeTypes";
import { TWebPage } from "../../types";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import {
  Modal,
  Button,
  ActionIcon,
  TextInput,
  Group,
  Stack,
  Text,
  ScrollArea,
  Badge,
} from "@mantine/core";
import {
  IconPlus,
  IconGlobe,
  IconEye,
  IconTrash,
  IconDeviceFloppy,
} from "@tabler/icons-react";

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
      // Reset transient input on close
      setUrlInput("");
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
            content: item.content ?? "",
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
    const selected = selectedUrls.map<TSpecifiedUrl>((url) => {
      const fetched = fetchedUrls.find((item) => item.url === url);
      return {
        url,
        content: fetched?.content,
      };
    });
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
      opened={isOpen}
      onClose={onClose}
      title={t("website-content-fetcher")}
      size="lg"
      centered
    >
      <Stack gap="md">
        <Group gap="xs">
          <TextInput
            placeholder={t("enter-website-url") || "Enter website URL"}
            value={urlInput}
            onChange={(e) => setUrlInput(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAddUrl();
            }}
            style={{ flex: 1 }}
          />
          <ActionIcon onClick={handleAddUrl} title={t("add-url") || "Add URL"}>
            <IconPlus size={18} />
          </ActionIcon>
        </Group>

        {/* Saved pages */}
        {isLoadingSaved && <Text size="xs">{t("loading") || "Loading..."}</Text>}
        {!isLoadingSaved && savedPages.length === 0 && (
          <Text size="xs" c="dimmed">{t("no-saved-pages-yet") || "No saved pages yet"}</Text>
        )}
        {savedPages.map((page) => {
          const fetched = fetchedUrls.find((f) => f.url === page.url);
          return (
            <div key={page.id} style={{ background: "var(--code-bg-color)", borderRadius: 8, padding: 8 }}>
              <Text size="xs" truncate title={page.url}>
                {page.title ? `${page.title} - ${page.url}` : page.url}
              </Text>
              <Group gap="xs" mt={4}>
                <Button
                  size="xs"
                  variant={selectedUrls.includes(page.url) ? "filled" : "default"}
                  leftSection={<IconGlobe size={14} />}
                  onClick={() => handleToggleSelected(page.url)}
                >
                  {selectedUrls.includes(page.url) ? t("selected") || "Selected" : t("select") || "Select"}
                </Button>
                {fetched?.status === "success" && fetched.content && (
                  <Button size="xs" variant="default" leftSection={<IconEye size={14} />} onClick={() => openContentModal(page.url, fetched.content)}>
                    {t("view") || "View"}
                  </Button>
                )}
                <ActionIcon variant="subtle" color="red" size="sm" onClick={() => handleDeleteSaved(page)} title={t("remove") || "Remove"}>
                  <IconTrash size={14} />
                </ActionIcon>
              </Group>
              {fetched?.status === "error" && fetched.errorMessage && (
                <Text size="xs" c="red" mt={4}>{fetched.errorMessage}</Text>
              )}
            </div>
          );
        })}

        {/* Unsaved fetched URLs */}
        {fetchedUrls
          .filter((f) => !savedPages.some((p) => p.url === f.url))
          .map((fetchedUrl, index) => (
            <div key={index} style={{ background: "var(--code-bg-color)", borderRadius: 8, padding: 8 }}>
              <Group gap="xs" align="center">
                <Text size="xs" truncate style={{ flex: 1 }} title={fetchedUrl.url}>
                  {fetchedUrl.url}
                </Text>
                {fetchedUrl.status === "pending" && <Badge size="xs" color="yellow">Pending</Badge>}
                {fetchedUrl.status === "error" && <Badge size="xs" color="red">{statusLabels.error}</Badge>}
              </Group>
              {fetchedUrl.status === "error" && fetchedUrl.errorMessage && (
                <Text size="xs" c="red" mt={4}>{fetchedUrl.errorMessage}</Text>
              )}
              <Group gap="xs" mt={4}>
                <Button
                  size="xs"
                  variant={selectedUrls.includes(fetchedUrl.url) ? "filled" : "default"}
                  leftSection={<IconGlobe size={14} />}
                  onClick={() => handleToggleSelected(fetchedUrl.url)}
                >
                  {selectedUrls.includes(fetchedUrl.url) ? t("selected") || "Selected" : t("select") || "Select"}
                </Button>
                {fetchedUrl.status === "success" && fetchedUrl.content && (
                  <Button size="xs" variant="default" leftSection={<IconEye size={14} />} onClick={() => openContentModal(fetchedUrl.url, fetchedUrl.content)}>
                    {t("view") || "View"}
                  </Button>
                )}
                <ActionIcon variant="subtle" color="red" size="sm" onClick={() => handleRemoveUrl(index)} title={t("remove") || "Remove"}>
                  <IconTrash size={14} />
                </ActionIcon>
                {fetchedUrl.status === "success" && fetchedUrl.content && !savedPages.some((p) => p.url === fetchedUrl.url) && (
                  <ActionIcon variant="subtle" color="green" size="sm" onClick={() => handleSavePage(fetchedUrl.url)} title={t("save") || "Save"}>
                    <IconDeviceFloppy size={14} />
                  </ActionIcon>
                )}
              </Group>
            </div>
          ))}

        {/* Content preview modal */}
        <Modal
          opened={contentModal.isOpen}
          onClose={() => setContentModal({ isOpen: false, url: "", content: "" })}
          title={t("inspect-content") || "Inspect content"}
          size="lg"
          centered
        >
          <Stack gap="sm">
            <Text size="xs" truncate title={contentModal.url}>{contentModal.url}</Text>
            <ScrollArea.Autosize mah={500}>
              <MarkdownRenderer markdown={contentModal.content} />
            </ScrollArea.Autosize>
          </Stack>
        </Modal>
      </Stack>
    </Modal>
  );
};
