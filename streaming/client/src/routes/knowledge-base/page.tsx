import React, { useState, useEffect, useRef, useMemo } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  getDocuments,
  uploadDocument,
  deleteDocument,
  getUserCompletions,
  updateCompletion,
  deleteCompletion,
  createCompletion,
  generateTrainingCompletions,
  getBigDocument,
  bulkDeleteCompletions,
  getTags,
} from "../../modules/apiCalls";
import { TDocument, TCompletion, TCompletionContextRules, TTag } from "../../types";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { TAgent } from "../../types/agents";
import { TemplatesTab } from "./TemplatesTab";
import { useSearchParams } from "react-router-dom";
import { useDisclosure, useMediaQuery } from "@mantine/hooks";
import { MobileFriendlyMultiSelect } from "../../components/MobileFriendlyMultiSelect/MobileFriendlyMultiSelect";

import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Checkbox,
  Group,
  Loader,
  Modal,
  NativeSelect,
  NumberInput,
  ScrollArea,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconCheck,
  IconClock,
  IconBarbell,
  IconEdit,
  IconFileText,
  IconHash,
  IconLoader,
  IconMenu2,
  IconPlus,
  IconRobot,
  IconSearch,
  IconSparkles,
  IconTemplate,
  IconTrash,
  IconUpload,
  IconX,
} from "@tabler/icons-react";

function agentIdsFromCompletion(c: TCompletion): string[] {
  if (Array.isArray(c.agent_ids)) {
    return c.agent_ids.map(String);
  }
  if (c.agent != null) {
    return [String(c.agent)];
  }
  return [];
}

function normalizeCompletion(raw: TCompletion): TCompletion {
  return {
    ...raw,
    agent_ids: Array.isArray(raw.agent_ids)
      ? raw.agent_ids
      : raw.agent != null
        ? [raw.agent]
        : [],
    context_rules: raw.context_rules ?? {
      include_always: false,
      include_for_tags: [],
    },
  };
}

function defaultContextRules(
  c: TCompletion
): TCompletionContextRules {
  return (
    c.context_rules ?? { include_always: false, include_for_tags: [] }
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const DOCS_POLL_INTERVAL_MS = 5000;
const DOCS_POLL_RECENT_WINDOW_MS = 10 * 60 * 1000;

const KNOWLEDGE_BASE_TAB_VALUES = [
  "documents",
  "completions",
  "templates",
] as const;

export type KnowledgeBaseTab = (typeof KNOWLEDGE_BASE_TAB_VALUES)[number];

/** Maps URL ?activeTab= (or legacy ?tab=) to KB section (default: documents). */
export function parseKnowledgeBaseActiveTab(
  searchParams: URLSearchParams
): KnowledgeBaseTab {
  const raw = (
    searchParams.get("activeTab") ||
    searchParams.get("tab") ||
    ""
  ).toLowerCase();
  if ((KNOWLEDGE_BASE_TAB_VALUES as readonly string[]).includes(raw)) {
    return raw as KnowledgeBaseTab;
  }
  return "documents";
}

export default function KnowledgeBasePage() {
  const { chatState, toggleSidebar, agents, fetchAgents } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = parseKnowledgeBaseActiveTab(searchParams);
  const [focusCompletionId, setFocusCompletionId] = useState<number | null>(null);

  const setKnowledgeBaseTab = (tab: KnowledgeBaseTab) => {
    const next = new URLSearchParams(searchParams);
    if (tab === "documents") {
      next.delete("activeTab");
    } else {
      next.set("activeTab", tab);
    }
    next.delete("tab");
    setSearchParams(next);
  };
  const [documents, setDocuments] = useState<TDocument[]>([]);
  const [completions, setCompletions] = useState<TCompletion[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingCompletions, setLoadingCompletions] = useState(true);
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("all");
  const [completionStatusFilter, setCompletionStatusFilter] = useState<
    "all" | "pending" | "approved"
  >("all");

  useEffect(() => {
    loadDocuments();
    loadCompletions();
    if (agents.length === 0) fetchAgents();
  }, []);

  useEffect(() => {
    const cid = searchParams.get("completion");
    if (cid && /^\d+$/.test(cid)) {
      setFocusCompletionId(parseInt(cid, 10));
      setCompletionStatusFilter("all");
    } else {
      setFocusCompletionId(null);
    }
  }, [searchParams]);

  useEffect(() => {
    const raw = searchParams.get("activeTab");
    if (!raw) return;
    if (parseKnowledgeBaseActiveTab(searchParams) !== raw.toLowerCase()) {
      const next = new URLSearchParams(searchParams);
      next.delete("activeTab");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const legacyTab = searchParams.get("tab");
    if (!legacyTab || searchParams.get("activeTab")) return;
    const next = new URLSearchParams(searchParams);
    next.delete("tab");
    const normalized = legacyTab.toLowerCase();
    if (
      normalized !== "documents" &&
      (KNOWLEDGE_BASE_TAB_VALUES as readonly string[]).includes(normalized)
    ) {
      next.set("activeTab", normalized);
    }
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const hasRecentProcessing = documents.some((doc) => {
      if (doc.brief?.trim()) return false;
      if (!doc.created_at) return false;
      const createdAt = Date.parse(doc.created_at);
      if (Number.isNaN(createdAt)) return false;
      return Date.now() - createdAt < DOCS_POLL_RECENT_WINDOW_MS;
    });

    if (!hasRecentProcessing) return;

    const id = window.setInterval(() => {
      loadDocuments({ silent: true });
    }, DOCS_POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [documents]);

  const loadDocuments = async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) setLoadingDocs(true);
    try {
      setDocuments(await getDocuments());
    } catch {
      toast.error(t("error-loading-documents"));
    } finally {
      if (!silent) setLoadingDocs(false);
    }
  };

  const loadCompletions = async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) setLoadingCompletions(true);
    try {
      const list = await getUserCompletions();
      setCompletions(list.map(normalizeCompletion));
    } catch {
      toast.error(t("error-loading-completions"));
    } finally {
      if (!silent) setLoadingCompletions(false);
    }
  };

  const patchCompletionInList = (updated: TCompletion) => {
    const normalized = normalizeCompletion(updated);
    setCompletions((prev) =>
      prev.map((c) => (c.id === normalized.id ? normalized : c))
    );
  };

  const removeCompletionFromList = (id: number) => {
    setCompletions((prev) => prev.filter((c) => c.id !== id));
  };

  const addCompletionToList = (created: TCompletion) => {
    setCompletions((prev) => [normalizeCompletion(created), ...prev]);
  };

  const filteredDocuments = documents.filter((doc) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      doc.name?.toLowerCase().includes(q) ||
      doc.brief?.toLowerCase().includes(q)
    );
  });

  const filteredCompletions = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = completions.filter((comp) => {
      const matchesSearch =
        !q ||
        comp.prompt.toLowerCase().includes(q) ||
        comp.answer.toLowerCase().includes(q);
      const matchesAgent =
        agentFilter === "all" ||
        (comp.agent_ids ?? []).map(String).includes(agentFilter);
      return matchesSearch && matchesAgent;
    });

    if (completionStatusFilter === "pending") {
      list = list.filter((c) => !c.approved);
    } else if (completionStatusFilter === "approved") {
      list = list.filter((c) => c.approved);
    }

    return [...list].sort((a, b) => {
      if (completionStatusFilter === "all") {
        const pa = a.approved ? 1 : 0;
        const pb = b.approved ? 1 : 0;
        if (pa !== pb) return pa - pb;
      }
      return b.id - a.id;
    });
  }, [completions, search, agentFilter, completionStatusFilter]);

  const completionStatusOptions: {
    value: typeof completionStatusFilter;
    label: string;
    hint: string;
  }[] = [
    { value: "all", label: t("all"), hint: t("completions-status-filter-all-help") },
    {
      value: "pending",
      label: t("pending"),
      hint: t("completions-status-filter-pending-help"),
    },
    {
      value: "approved",
      label: t("approved"),
      hint: t("completions-status-filter-approved-help"),
    },
  ];

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          padding: 24,
          overflowY: "auto",
          minHeight: "100vh",
          display: "flex",
          justifyContent: "center",
        }}
        className="relative"
      >
        {!chatState.isSidebarOpened && (
          <Box pos="absolute" top={24} left={24} style={{ zIndex: 10 }}>
            <ActionIcon variant="subtle" color="gray" onClick={toggleSidebar}>
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box px="md" w="100%" maw="52rem" mx="auto">
          <Title order={2} ta="center" mb="xs" mt="md">
            {t("knowledge-base")}
          </Title>
          <Text ta="center" c="dimmed" mb="lg" size="sm">
            {t("knowledge-base-description")}
          </Text>

          {/* Tabs */}
          <Group gap="xs" mb="md">
            <Button
              variant={activeTab === "documents" ? "filled" : "default"}
              leftSection={<IconFileText size={16} />}
              size="sm"
              onClick={() => setKnowledgeBaseTab("documents")}
            >
              {t("documents")} ({documents.length})
            </Button>
            <Button
              variant={activeTab === "completions" ? "filled" : "default"}
              leftSection={<IconSparkles size={16} />}
              size="sm"
              onClick={() => setKnowledgeBaseTab("completions")}
            >
              {t("completions")} ({completions.length})
            </Button>
            <Button
              variant={activeTab === "templates" ? "filled" : "default"}
              leftSection={<IconTemplate size={16} />}
              size="sm"
              onClick={() => setKnowledgeBaseTab("templates")}
            >
              {t("document-templates-tab")}
            </Button>
          </Group>

          {/* Filters */}
          <Group gap="sm" mb="md">
            <TextInput
              placeholder={t("search")}
              leftSection={<IconSearch size={16} />}
              value={search}
              onChange={(e) => setSearch(e.currentTarget.value)}
              style={{ flex: 1, minWidth: 200 }}
              size="sm"
            />
            {activeTab === "completions" && (
              <NativeSelect
                value={agentFilter}
                onChange={(e) => setAgentFilter(e.currentTarget.value)}
                data={[
                  { value: "all", label: t("all-agents") },
                  ...agents
                    .filter((a) => a.id)
                    .map((a) => ({
                      value: a.id!.toString(),
                      label: a.name,
                    })),
                ]}
                size="sm"
              />
            )}
          </Group>

          {activeTab === "completions" && (
            <Group justify="center" wrap="wrap" gap="xs" mb="md">
              {completionStatusOptions.map((opt) => (
                <Tooltip key={opt.value} label={opt.hint} withArrow>
                  <Button
                    variant={
                      completionStatusFilter === opt.value ? "filled" : "default"
                    }
                    size="xs"
                    onClick={() => setCompletionStatusFilter(opt.value)}
                  >
                    {opt.label}
                  </Button>
                </Tooltip>
              ))}
            </Group>
          )}

          {/* Content */}
          {activeTab === "documents" ? (
            <DocumentsTab
              documents={filteredDocuments}
              loading={loadingDocs}
              onRefresh={loadDocuments}
              agents={agents}
            />
          ) : activeTab === "completions" ? (
            <CompletionsTab
              completions={filteredCompletions}
              anyCompletionsExist={completions.length > 0}
              loading={loadingCompletions}
              onCompletionPatched={patchCompletionInList}
              onCompletionRemoved={removeCompletionFromList}
              onCompletionAdded={addCompletionToList}
              onBulkRemoved={(ids) =>
                setCompletions((prev) => prev.filter((c) => !ids.has(c.id)))
              }
              agents={agents}
              focusCompletionId={focusCompletionId}
            />
          ) : (
            <TemplatesTab agents={agents} filterQuery={search} />
          )}
        </Box>
      </div>
    </main>
  );
}

// ─── Documents Tab ────────────────────────────────────────────────────────────

const DocumentsTab = ({
  documents,
  loading,
  onRefresh,
  agents,
}: {
  documents: TDocument[];
  loading: boolean;
  onRefresh: () => void;
  agents: TAgent[];
}) => {
  const { t } = useTranslation();
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    const toastId = toast.loading(t("uploading-document"));
    try {
      for (const file of Array.from(files)) {
        const fd = new FormData();
        fd.append("file", file);
        await uploadDocument(fd);
      }
      toast.success(t("document-uploaded"));
      onRefresh();
    } catch {
      toast.error(t("error-uploading-document"));
    } finally {
      toast.dismiss(toastId);
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFileUpload(e.dataTransfer.files);
  };

  const handleDelete = async (docId: number) => {
    const toastId = toast.loading(t("deleting-document"));
    try {
      await deleteDocument(docId);
      toast.success(t("document-deleted"));
      onRefresh();
    } catch {
      toast.error(t("error-deleting-document"));
    } finally {
      toast.dismiss(toastId);
    }
  };

  if (loading) {
    return (
      <Stack align="center" py="xl">
        <Loader color="violet" />
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      {/* Upload area */}
      <Card
        withBorder
        p="xl"
        ta="center"
        style={{
          cursor: "pointer",
          borderStyle: "dashed",
          borderColor: dragging
            ? "var(--mantine-color-violet-6)"
            : undefined,
          background: dragging
            ? "rgba(110,91,255,0.06)"
            : undefined,
        }}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          style={{ display: "none" }}
          onChange={(e) => handleFileUpload(e.target.files)}
        />
        <IconUpload
          size={32}
          style={{ margin: "0 auto 8px", opacity: 0.4 }}
        />
        <Text c="dimmed" size="sm">
          {uploading
            ? t("uploading") + "..."
            : t("drag-drop-or-click-to-upload")}
        </Text>
      </Card>

      {/* Documents list */}
      {documents.length === 0 ? (
        <Card withBorder p="xl" ta="center" style={{ borderStyle: "dashed" }}>
          <Text c="dimmed">{t("no-documents-yet")}</Text>
        </Card>
      ) : (
        documents.map((doc) => (
          <DocumentItem
            key={doc.id}
            document={doc}
            agents={agents}
            onDelete={() => handleDelete(doc.id)}
          />
        ))
      )}
    </Stack>
  );
};

// ─── Document Item ────────────────────────────────────────────────────────────

const DocumentItem = ({
  document,
  agents,
  onDelete,
}: {
  document: TDocument;
  agents: TAgent[];
  onDelete: () => void;
}) => {
  const { t } = useTranslation();
  const [showChunks, setShowChunks] = useState(false);
  const [showTraining, setShowTraining] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const isProcessing = !document.brief;

  return (
    <>
      <ChunksModal
        opened={showChunks}
        onClose={() => setShowChunks(false)}
        documentId={document.id}
      />
      <TrainingModal
        opened={showTraining}
        onClose={() => setShowTraining(false)}
        document={document}
        agents={agents}
      />

      <Card withBorder p="md">
        <Text fw={600} mb={4}>
          {document.name || t("untitled")}
        </Text>

        <Group gap={6} mb="xs">
          <Badge
            size="xs"
            variant="default"
            leftSection={<IconFileText size={10} />}
          >
            {document.chunk_count} {t("chunks")}
          </Badge>
          <Badge
            size="xs"
            variant="default"
            leftSection={<IconHash size={10} />}
          >
            {document.total_tokens} {t("tokens")}
          </Badge>
          {isProcessing && (
            <Badge
              size="xs"
              variant="light"
              color="yellow"
              leftSection={<IconLoader size={10} />}
            >
              {t("processing")}
            </Badge>
          )}
        </Group>

        {document.brief && (
          <Text size="sm" c="dimmed" mb="sm" lineClamp={3}>
            {document.brief}
          </Text>
        )}

        <Group gap="xs">
          <Button
            variant="default"
            size="xs"
            leftSection={<IconSearch size={14} />}
            onClick={() => setShowChunks(true)}
            disabled={isProcessing}
          >
            {t("show-document-text")}
          </Button>
          <Button
            variant="default"
            size="xs"
            leftSection={<IconBarbell size={14} />}
            onClick={() => setShowTraining(true)}
            disabled={isProcessing}
          >
            {t("train-on-this-document")}
          </Button>
          <Button
            variant="light"
            color={confirmDelete ? "red" : "gray"}
            size="xs"
            leftSection={<IconTrash size={14} />}
            onClick={() => {
              if (confirmDelete) {
                onDelete();
                setConfirmDelete(false);
              } else {
                setConfirmDelete(true);
              }
            }}
            onBlur={() => setConfirmDelete(false)}
          >
            {confirmDelete ? t("im-sure") : t("delete")}
          </Button>
        </Group>
      </Card>
    </>
  );
};

// ─── Chunks Modal ─────────────────────────────────────────────────────────────

const ChunksModal = ({
  opened,
  onClose,
  documentId,
}: {
  opened: boolean;
  onClose: () => void;
  documentId: number;
}) => {
  const { t } = useTranslation();
  const [chunks, setChunks] = useState<{ id: number; content: string }[]>([]);
  const [filtered, setFiltered] = useState<{ id: number; content: string }[]>(
    []
  );
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!opened) return;
    getBigDocument(documentId.toString()).then((doc) => {
      const c = doc.chunk_set || [];
      setChunks(c);
      setFiltered(c);
    });
  }, [opened, documentId]);

  useEffect(() => {
    setFiltered(
      chunks.filter((c) =>
        c.content.toLowerCase().includes(search.toLowerCase())
      )
    );
  }, [search, chunks]);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t("document-chunks")}
      size="lg"
    >
      <Stack gap="sm">
        <Group gap="xs">
          <TextInput
            placeholder={t("find-something-in-the-document")}
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
            style={{ flex: 1 }}
            size="sm"
          />
          <Badge variant="default" size="lg">
            {filtered.length} / {chunks.length}
          </Badge>
        </Group>

        <ScrollArea.Autosize mah="60vh">
          <Stack gap="xs">
            {filtered.map((c) => (
              <ChunkItem key={c.id} content={c.content} id={c.id} />
            ))}
          </Stack>
        </ScrollArea.Autosize>
      </Stack>
    </Modal>
  );
};

const ChunkItem = ({ content, id }: { content: string; id: number }) => {
  const [full, setFull] = useState(false);

  return (
    <Card
      withBorder
      p="sm"
      style={{ cursor: "pointer" }}
      onClick={() => setFull(!full)}
    >
      <Text
        size="sm"
        style={{ whiteSpace: "pre-wrap", fontFamily: "monospace" }}
      >
        {full ? content : content.slice(0, 200)}
        {!full && content.length > 200 && "..."}
      </Text>
    </Card>
  );
};

// ─── Training Modal ───────────────────────────────────────────────────────────

const TrainingModal = ({
  opened,
  onClose,
  document,
  agents,
}: {
  opened: boolean;
  onClose: () => void;
  document: TDocument;
  agents: TAgent[];
}) => {
  const { t } = useTranslation();
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [target, setTarget] = useState(30);
  const [generating, setGenerating] = useState(false);

  const toggleAgent = (slug: string) => {
    setSelectedAgents((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  };

  const handleGenerate = async () => {
    if (selectedAgents.length === 0) {
      toast.error(t("please-select-at-least-one-agent"));
      return;
    }
    setGenerating(true);
    try {
      await generateTrainingCompletions({
        model_id: document.id.toString(),
        db_model: "document",
        agents: selectedAgents,
        completions_target_number: target,
      });
      toast.success(t("training-generation-in-queue"));
      onClose();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t("train-on-this-document")}
      size="md"
    >
      <Stack gap="md">
        <Text size="sm">
          {t("generate-completions-description")}{" "}
          <Text span fw={600}>
            {document.name}
          </Text>{" "}
          {t("generate-completions-description-2")}
        </Text>
        <Text size="sm" c="dimmed">
          {t("after-generating-completions")}
        </Text>

        <NumberInput
          label={t("number-of-completions-to-generate")}
          value={target}
          onChange={(val) => setTarget(typeof val === "number" ? val : 30)}
          min={1}
          variant="filled"
        />

        <Text size="sm" fw={500}>
          {t("select-agents-that-will-retrain")}
        </Text>
        <Group gap="xs">
          {agents.map((a) => (
            <Badge
              key={a.slug}
              variant={selectedAgents.includes(a.slug) ? "filled" : "default"}
              style={{ cursor: "pointer" }}
              onClick={() => toggleAgent(a.slug)}
            >
              {a.name}
            </Badge>
          ))}
        </Group>

        <Button
          leftSection={<IconBarbell size={16} />}
          onClick={handleGenerate}
          loading={generating}
          fullWidth
        >
          {t("generate")}
        </Button>
      </Stack>
    </Modal>
  );
};

// ─── Completions Tab ──────────────────────────────────────────────────────────

const CompletionsTab = ({
  completions,
  anyCompletionsExist,
  loading,
  onCompletionPatched,
  onCompletionRemoved,
  onCompletionAdded,
  onBulkRemoved,
  agents,
  focusCompletionId,
}: {
  completions: TCompletion[];
  anyCompletionsExist: boolean;
  loading: boolean;
  onCompletionPatched: (updated: TCompletion) => void;
  onCompletionRemoved: (id: number) => void;
  onCompletionAdded: (created: TCompletion) => void;
  onBulkRemoved: (ids: Set<number>) => void;
  agents: TAgent[];
  focusCompletionId: number | null;
}) => {
  const { t } = useTranslation();
  const [showCreate, setShowCreate] = useState(false);
  const [newPrompt, setNewPrompt] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [newAgentIds, setNewAgentIds] = useState<string[]>([]);
  const [newContextRules, setNewContextRules] = useState<TCompletionContextRules>({
    include_always: false,
    include_for_tags: [],
  });
  const [orgTags, setOrgTags] = useState<TTag[]>([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    getTags()
      .then((tags) => setOrgTags(tags))
      .catch(() => setOrgTags([]));
  }, []);

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);

  const allSelected =
    completions.length > 0 && selectedIds.size === completions.length;
  const someSelected = selectedIds.size > 0;

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setConfirmBulkDelete(false);
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(completions.map((c) => c.id)));
    }
    setConfirmBulkDelete(false);
  };

  const handleBulkDelete = async () => {
    if (!confirmBulkDelete) {
      setConfirmBulkDelete(true);
      return;
    }
    setBulkDeleting(true);
    const toastId = toast.loading(t("deleting-completions"));
    try {
      await bulkDeleteCompletions(Array.from(selectedIds));
      toast.success(
        t("completions-deleted", { count: selectedIds.size })
      );
      const deleted = new Set(selectedIds);
      setSelectedIds(new Set());
      setConfirmBulkDelete(false);
      onBulkRemoved(deleted);
    } catch {
      toast.error(t("error-deleting-completions"));
    } finally {
      toast.dismiss(toastId);
      setBulkDeleting(false);
    }
  };

  const handleCreate = async () => {
    if (!newPrompt.trim() || !newAnswer.trim()) {
      toast.error(t("prompt-and-answer-required"));
      return;
    }
    setCreating(true);
    try {
      const created = await createCompletion({
        prompt: newPrompt,
        answer: newAnswer,
        agents: newAgentIds.map((id) => parseInt(id, 10)),
        context_rules: newContextRules,
        approved: false,
      });
      onCompletionAdded(created);
      toast.success(t("completion-created"));
      setNewPrompt("");
      setNewAnswer("");
      setNewAgentIds([]);
      setNewContextRules({ include_always: false, include_for_tags: [] });
      setShowCreate(false);
    } catch {
      toast.error(t("error-creating-completion"));
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <Stack align="center" py="xl">
        <Loader color="violet" />
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      {/* Action bar */}
      <Group justify="space-between">
        <Group gap="xs">
          {completions.length > 0 && (
            <Checkbox
              checked={allSelected}
              indeterminate={someSelected && !allSelected}
              onChange={toggleSelectAll}
              label={allSelected ? t("unselect-all") : t("select-all")}
              size="sm"
            />
          )}
          {someSelected && (
            <Button
              variant="light"
              color={confirmBulkDelete ? "red" : "red"}
              size="xs"
              leftSection={<IconTrash size={14} />}
              loading={bulkDeleting}
              onClick={handleBulkDelete}
              onBlur={() => setConfirmBulkDelete(false)}
            >
              {confirmBulkDelete
                ? t("confirm-delete-count", { count: selectedIds.size })
                : t("delete-selected", { count: selectedIds.size })}
            </Button>
          )}
        </Group>

        {!showCreate && (
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => setShowCreate(true)}
            size="sm"
          >
            {t("new-completion")}
          </Button>
        )}
      </Group>

      {showCreate && (
        <Card withBorder p="lg">
          <Title order={4} mb="md">
            {t("create-completion")}
          </Title>
          <Stack gap="sm">
            <Textarea
              label={t("prompt")}
              placeholder={t("prompt-placeholder")}
              value={newPrompt}
              onChange={(e) => setNewPrompt(e.currentTarget.value)}
              minRows={2}
              autosize
            />
            <Textarea
              label={t("answer")}
              placeholder={t("answer-placeholder")}
              value={newAnswer}
              onChange={(e) => setNewAnswer(e.currentTarget.value)}
              minRows={3}
              autosize
            />
            <MobileFriendlyMultiSelect
              label={t("assign-to-agents")}
              placeholder={t("select-agents")}
              pickerTitle={t("assign-to-agents")}
              value={newAgentIds}
              onChange={setNewAgentIds}
              data={agents
                .filter((a) => a.id)
                .map((a) => ({
                  value: a.id!.toString(),
                  label: a.name,
                }))}
            />
            <Checkbox
              label={t("completion-include-always")}
              checked={newContextRules.include_always}
              onChange={(e) =>
                setNewContextRules((prev) => ({
                  ...prev,
                  include_always: e.currentTarget.checked,
                }))
              }
            />
            <MobileFriendlyMultiSelect
              label={t("completion-include-for-tags")}
              description={t("completion-include-for-tags-help")}
              pickerTitle={t("completion-include-for-tags")}
              value={newContextRules.include_for_tags.map(String)}
              onChange={(vals) =>
                setNewContextRules((prev) => ({
                  ...prev,
                  include_for_tags: vals.map((v) => parseInt(v, 10)),
                }))
              }
              data={orgTags
                .filter((tag) => tag.enabled)
                .map((tag) => ({
                  value: tag.id.toString(),
                  label: tag.title,
                }))}
              disabled={newContextRules.include_always}
            />
            <Group justify="flex-end">
              <Button
                variant="default"
                onClick={() => {
                  setShowCreate(false);
                  setNewPrompt("");
                  setNewAnswer("");
                  setNewAgentIds([]);
                  setNewContextRules({
                    include_always: false,
                    include_for_tags: [],
                  });
                }}
              >
                {t("cancel")}
              </Button>
              <Button onClick={handleCreate} loading={creating}>
                {t("create")}
              </Button>
            </Group>
          </Stack>
        </Card>
      )}

      {completions.length === 0 && !showCreate && !anyCompletionsExist ? (
        <Card withBorder p="xl" ta="center" style={{ borderStyle: "dashed" }}>
          <Text c="dimmed">{t("no-completions-yet")}</Text>
          <Text size="sm" c="dimmed" mt="xs">
            {t("completions-hint")}
          </Text>
        </Card>
      ) : completions.length === 0 && !showCreate && anyCompletionsExist ? (
        <Card withBorder p="xl" ta="center" style={{ borderStyle: "dashed" }}>
          <Text c="dimmed">{t("no-completions-match-filters")}</Text>
        </Card>
      ) : (
        completions.map((comp) => (
          <CompletionItem
            key={comp.id}
            completion={comp}
            agents={agents}
            orgTags={orgTags}
            onPatched={onCompletionPatched}
            onRemoved={onCompletionRemoved}
            selected={selectedIds.has(comp.id)}
            onToggleSelect={() => toggleSelect(comp.id)}
            focusCompletionId={focusCompletionId}
          />
        ))
      )}
    </Stack>
  );
};

// ─── Completion approval (two-sided + switch) ─────────────────────────────────

const CompletionApprovalToggle = ({
  approved,
  onChange,
}: {
  approved: boolean;
  onChange: (approved: boolean) => void;
}) => {
  const { t } = useTranslation();

  const sideStyle = (active: boolean, accent: "yellow" | "green") => ({
    flex: 1,
    minWidth: 0,
    padding: "10px 12px",
    borderRadius: "var(--mantine-radius-md)",
    cursor: "pointer",
    border: `1px solid ${
      active
        ? `var(--mantine-color-${accent}-6)`
        : "var(--mantine-color-dark-4)"
    }`,
    background: active
      ? `var(--mantine-color-${accent}-light)`
      : "var(--mantine-color-dark-7)",
    opacity: active ? 1 : 0.55,
    transition: "border-color 150ms, background 150ms, opacity 150ms",
  });

  return (
    <Group align="center" gap="sm" wrap="nowrap" w="100%">
      <Box
        style={sideStyle(!approved, "yellow")}
        onClick={() => onChange(false)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onChange(false);
          }
        }}
      >
        <Text
          size="sm"
          fw={600}
          c={!approved ? "yellow.4" : "dimmed"}
          mb={4}
        >
          {t("completion-status-pending")}
        </Text>
        <Text size="xs" c="dimmed" lh={1.4}>
          {t("completion-approved-toggle-off")}
        </Text>
      </Box>

      <Switch
        checked={approved}
        onChange={(e) => onChange(e.currentTarget.checked)}
        size="md"
        color="green"
        styles={{ root: { flexShrink: 0 } }}
        aria-label={t("approved")}
      />

      <Box
        style={sideStyle(approved, "green")}
        onClick={() => onChange(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onChange(true);
          }
        }}
      >
        <Text
          size="sm"
          fw={600}
          c={approved ? "green.4" : "dimmed"}
          mb={4}
        >
          {t("completion-status-approved")}
        </Text>
        <Text size="xs" c="dimmed" lh={1.4}>
          {t("completion-approved-toggle-on")}
        </Text>
      </Box>
    </Group>
  );
};

// ─── Completion Item ──────────────────────────────────────────────────────────

const CompletionItem = ({
  completion,
  agents,
  orgTags,
  onPatched,
  onRemoved,
  selected,
  onToggleSelect,
  focusCompletionId,
}: {
  completion: TCompletion;
  agents: TAgent[];
  orgTags: TTag[];
  onPatched: (updated: TCompletion) => void;
  onRemoved: (id: number) => void;
  selected: boolean;
  onToggleSelect: () => void;
  focusCompletionId: number | null;
}) => {
  const { t } = useTranslation();
  const isMobile = useMediaQuery("(max-width: 48em)");
  const [editOpened, { open: openEdit, close: closeEdit }] = useDisclosure(false);
  const [prompt, setPrompt] = useState(completion.prompt);
  const [answer, setAnswer] = useState(completion.answer);
  const [agentIds, setAgentIds] = useState<string[]>(() =>
    agentIdsFromCompletion(completion)
  );
  const [contextRules, setContextRules] = useState<TCompletionContextRules>(() =>
    defaultContextRules(completion)
  );
  const [approved, setApproved] = useState(completion.approved);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const didAutoFocusRef = useRef(false);

  const resetDraftFromCompletion = (c: TCompletion) => {
    setPrompt(c.prompt);
    setAnswer(c.answer);
    setAgentIds(agentIdsFromCompletion(c));
    setContextRules(defaultContextRules(c));
    setApproved(c.approved);
  };

  useEffect(() => {
    if (editOpened) return;
    resetDraftFromCompletion(completion);
  }, [completion, editOpened]);

  useEffect(() => {
    if (focusCompletionId == null) {
      didAutoFocusRef.current = false;
    }
  }, [focusCompletionId]);

  useEffect(() => {
    if (focusCompletionId !== completion.id) return;
    if (didAutoFocusRef.current) return;
    didAutoFocusRef.current = true;
    const timer = window.setTimeout(() => {
      cardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      openEdit();
    }, 200);
    return () => window.clearTimeout(timer);
  }, [focusCompletionId, completion.id]);

  const savedAgentIds = agentIdsFromCompletion(completion);
  const savedRules = defaultContextRules(completion);

  const assignedAgentNames = agents
    .filter((a) =>
      a.id && savedAgentIds.includes(a.id.toString())
    )
    .map((a) => a.name);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await updateCompletion(completion.id.toString(), {
        prompt,
        answer,
        approved,
        agents: agentIds.map((id) => parseInt(id, 10)),
        context_rules: contextRules,
      });
      onPatched(updated);
      toast.success(t("completion-updated"));
      closeEdit();
      resetDraftFromCompletion(normalizeCompletion(updated));
    } catch {
      toast.error(t("error-updating-completion"));
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async () => {
    const nextApproved = !completion.approved;
    try {
      const updated = await updateCompletion(completion.id.toString(), {
        prompt: completion.prompt,
        answer: completion.answer,
        approved: nextApproved,
        agents: savedAgentIds.map((id) => parseInt(id, 10)),
        context_rules: savedRules,
      });
      onPatched(updated);
      toast.success(
        nextApproved ? t("completion-approved") : t("completion-unapproved")
      );
    } catch {
      toast.error(t("error-updating-completion"));
    }
  };

  const handleCancelEdit = () => {
    resetDraftFromCompletion(completion);
    closeEdit();
  };

  const handleDelete = async () => {
    try {
      await deleteCompletion(completion.id.toString());
      onRemoved(completion.id);
      toast.success(t("completion-deleted"));
    } catch {
      toast.error(t("error-deleting-completion"));
    }
  };

  return (
    <Card
      ref={cardRef}
      withBorder
      p="md"
      style={{
        borderColor: selected ? "var(--mantine-color-violet-6)" : undefined,
      }}
    >
      <Group gap="sm" align="flex-start" wrap="nowrap">
        <Checkbox
          checked={selected}
          onChange={onToggleSelect}
          mt={4}
          style={{ flexShrink: 0 }}
        />
        <Box style={{ flex: 1, minWidth: 0 }}>
      <Text fw={600} mb={4}>
        {completion.prompt}
      </Text>

      {/* Status badges */}
      <Group gap={6} mb="xs">
        <Badge
          size="xs"
          variant="light"
          color={completion.approved ? "green" : "yellow"}
          leftSection={
            completion.approved ? (
              <IconCheck size={10} />
            ) : (
              <IconClock size={10} />
            )
          }
        >
          {completion.approved ? t("approved") : t("pending")}
        </Badge>
        {assignedAgentNames.map((name) => (
          <Badge
            key={name}
            size="xs"
            variant="default"
            leftSection={<IconRobot size={10} />}
          >
            {name}
          </Badge>
        ))}
        {savedRules.include_always && (
          <Badge size="xs" variant="light" color="violet">
            {t("completion-include-always")}
          </Badge>
        )}
        {savedRules.include_for_tags.length > 0 && (
          <Badge size="xs" variant="light" color="blue">
            {t("completion-tag-rules-count", {
              count: savedRules.include_for_tags.length,
            })}
          </Badge>
        )}
      </Group>

      <Text size="sm" c="dimmed" mb="sm" style={{ whiteSpace: "pre-wrap" }}>
        {completion.answer}
      </Text>

      <Group gap="xs" wrap="wrap">
        <Button
          variant="light"
          color={completion.approved ? "green" : "gray"}
          size="xs"
          leftSection={
            completion.approved ? (
              <IconX size={14} />
            ) : (
              <IconCheck size={14} />
            )
          }
          onClick={handleApprove}
        >
          {completion.approved ? t("unapprove") : t("approve")}
        </Button>

        <Button
          variant="default"
          size="xs"
          leftSection={<IconEdit size={14} />}
          onClick={openEdit}
        >
          {t("edit")}
        </Button>

        <Button
          variant="light"
          color={confirmDelete ? "red" : "gray"}
          size="xs"
          leftSection={<IconTrash size={14} />}
          onClick={() => {
            if (confirmDelete) {
              handleDelete();
              setConfirmDelete(false);
            } else {
              setConfirmDelete(true);
            }
          }}
          onBlur={() => setConfirmDelete(false)}
        >
          {confirmDelete ? t("im-sure") : t("delete")}
        </Button>
      </Group>
        </Box>
      </Group>

      <Modal
        opened={editOpened}
        onClose={handleCancelEdit}
        title={
          <Group gap="xs">
            <IconEdit size={18} />
            <Text fw={600} size="sm">
              {t("edit")} — {t("completion")} {completion.id}
            </Text>
          </Group>
        }
        centered
        size="lg"
        fullScreen={isMobile}
      >
        <Stack gap="md">
          <Textarea
            label={t("prompt")}
            placeholder={t("prompt-placeholder")}
            value={prompt}
            onChange={(e) => setPrompt(e.currentTarget.value)}
            minRows={3}
            autosize
          />
          <Textarea
            label={t("answer")}
            placeholder={t("answer-placeholder")}
            value={answer}
            onChange={(e) => setAnswer(e.currentTarget.value)}
            minRows={4}
            autosize
          />
          <CompletionApprovalToggle
            approved={approved}
            onChange={setApproved}
          />
          <MobileFriendlyMultiSelect
            label={t("assign-to-agents")}
            placeholder={t("select-agents")}
            pickerTitle={t("assign-to-agents")}
            value={agentIds}
            onChange={setAgentIds}
            data={agents
              .filter((a) => a.id)
              .map((a) => ({
                value: a.id!.toString(),
                label: a.name,
              }))}
          />
          <Checkbox
            label={t("completion-include-always")}
            checked={contextRules.include_always}
            onChange={(e) =>
              setContextRules({
                ...contextRules,
                include_always: e.currentTarget.checked,
                include_for_tags: e.currentTarget.checked
                  ? []
                  : contextRules.include_for_tags,
              })
            }
          />
          <MobileFriendlyMultiSelect
            label={t("completion-include-for-tags")}
            description={t("completion-include-for-tags-help")}
            pickerTitle={t("completion-include-for-tags")}
            value={contextRules.include_for_tags.map(String)}
            onChange={(vals) =>
              setContextRules({
                ...contextRules,
                include_for_tags: vals.map((v) => parseInt(v, 10)),
              })
            }
            data={orgTags
              .filter((tag) => tag.enabled)
              .map((tag) => ({
                value: tag.id.toString(),
                label: tag.title,
              }))}
            disabled={contextRules.include_always}
          />
          <Group justify="flex-end" gap="sm">
            <Button
              variant="default"
              onClick={handleCancelEdit}
              disabled={saving}
            >
              {t("cancel")}
            </Button>
            <Button onClick={handleSave} loading={saving}>
              {t("save")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Card>
  );
};
