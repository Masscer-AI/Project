import React, { useState, useEffect, useRef } from "react";
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
} from "../../modules/apiCalls";
import { TDocument, TCompletion } from "../../types";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { TAgent } from "../../types/agents";

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
  IconTrash,
  IconUpload,
  IconX,
} from "@tabler/icons-react";

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function KnowledgeBasePage() {
  const { chatState, toggleSidebar, agents, fetchAgents } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"documents" | "completions">(
    "documents"
  );
  const [documents, setDocuments] = useState<TDocument[]>([]);
  const [completions, setCompletions] = useState<TCompletion[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingCompletions, setLoadingCompletions] = useState(true);
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("all");

  useEffect(() => {
    loadDocuments();
    loadCompletions();
    if (agents.length === 0) fetchAgents();
  }, []);

  useEffect(() => {
    const hasProcessing = documents.some((doc) => !doc.brief);
    if (!hasProcessing) return;
    const id = window.setInterval(loadDocuments, 5000);
    return () => window.clearInterval(id);
  }, [documents]);

  const loadDocuments = async () => {
    setLoadingDocs(true);
    try {
      setDocuments(await getDocuments());
    } catch {
      toast.error(t("error-loading-documents"));
    } finally {
      setLoadingDocs(false);
    }
  };

  const loadCompletions = async () => {
    setLoadingCompletions(true);
    try {
      setCompletions(await getUserCompletions());
    } catch {
      toast.error(t("error-loading-completions"));
    } finally {
      setLoadingCompletions(false);
    }
  };

  const filteredDocuments = documents.filter((doc) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      doc.name?.toLowerCase().includes(q) ||
      doc.brief?.toLowerCase().includes(q)
    );
  });

  const filteredCompletions = completions.filter((comp) => {
    const matchesSearch =
      comp.prompt.toLowerCase().includes(search.toLowerCase()) ||
      comp.answer.toLowerCase().includes(search.toLowerCase());
    const matchesAgent =
      agentFilter === "all" || comp.agent?.toString() === agentFilter;
    return matchesSearch && matchesAgent;
  });

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
              onClick={() => setActiveTab("documents")}
            >
              {t("documents")} ({documents.length})
            </Button>
            <Button
              variant={activeTab === "completions" ? "filled" : "default"}
              leftSection={<IconSparkles size={16} />}
              size="sm"
              onClick={() => setActiveTab("completions")}
            >
              {t("completions")} ({completions.length})
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

          {/* Content */}
          {activeTab === "documents" ? (
            <DocumentsTab
              documents={filteredDocuments}
              loading={loadingDocs}
              onRefresh={loadDocuments}
              agents={agents}
            />
          ) : (
            <CompletionsTab
              completions={filteredCompletions}
              loading={loadingCompletions}
              onRefresh={loadCompletions}
              agents={agents}
            />
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
  loading,
  onRefresh,
  agents,
}: {
  completions: TCompletion[];
  loading: boolean;
  onRefresh: () => void;
  agents: TAgent[];
}) => {
  const { t } = useTranslation();
  const [showCreate, setShowCreate] = useState(false);
  const [newPrompt, setNewPrompt] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [newAgentId, setNewAgentId] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    if (!newPrompt.trim() || !newAnswer.trim()) {
      toast.error(t("prompt-and-answer-required"));
      return;
    }
    setCreating(true);
    try {
      await createCompletion({
        prompt: newPrompt,
        answer: newAnswer,
        agent: newAgentId ? parseInt(newAgentId) : null,
        approved: false,
      });
      toast.success(t("completion-created"));
      setNewPrompt("");
      setNewAnswer("");
      setNewAgentId("");
      setShowCreate(false);
      onRefresh();
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
      {!showCreate && (
        <Group justify="flex-end">
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => setShowCreate(true)}
          >
            {t("new-completion")}
          </Button>
        </Group>
      )}

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
            <NativeSelect
              label={t("assign-to-agent")}
              value={newAgentId}
              onChange={(e) => setNewAgentId(e.currentTarget.value)}
              data={[
                { value: "", label: t("no-agent-assigned") },
                ...agents
                  .filter((a) => a.id)
                  .map((a) => ({
                    value: a.id!.toString(),
                    label: a.name,
                  })),
              ]}
            />
            <Group justify="flex-end">
              <Button
                variant="default"
                onClick={() => {
                  setShowCreate(false);
                  setNewPrompt("");
                  setNewAnswer("");
                  setNewAgentId("");
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

      {completions.length === 0 && !showCreate ? (
        <Card withBorder p="xl" ta="center" style={{ borderStyle: "dashed" }}>
          <Text c="dimmed">{t("no-completions-yet")}</Text>
          <Text size="sm" c="dimmed" mt="xs">
            {t("completions-hint")}
          </Text>
        </Card>
      ) : (
        completions.map((comp) => (
          <CompletionItem
            key={comp.id}
            completion={comp}
            agents={agents}
            onRefresh={onRefresh}
          />
        ))
      )}
    </Stack>
  );
};

// ─── Completion Item ──────────────────────────────────────────────────────────

const CompletionItem = ({
  completion,
  agents,
  onRefresh,
}: {
  completion: TCompletion;
  agents: TAgent[];
  onRefresh: () => void;
}) => {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [prompt, setPrompt] = useState(completion.prompt);
  const [answer, setAnswer] = useState(completion.answer);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const agentName = agents.find((a) => a.id === completion.agent)?.name;

  const handleSave = async () => {
    try {
      await updateCompletion(completion.id.toString(), {
        prompt,
        answer,
        approved: completion.approved,
      });
      toast.success(t("completion-updated"));
      setIsEditing(false);
      onRefresh();
    } catch {
      toast.error(t("error-updating-completion"));
    }
  };

  const handleApprove = async () => {
    try {
      await updateCompletion(completion.id.toString(), {
        prompt: completion.prompt,
        answer: completion.answer,
        approved: !completion.approved,
      });
      toast.success(
        completion.approved ? t("completion-unapproved") : t("completion-approved")
      );
      onRefresh();
    } catch {
      toast.error(t("error-updating-completion"));
    }
  };

  const handleAssignAgent = async (agentId: string) => {
    try {
      await updateCompletion(completion.id.toString(), {
        prompt: completion.prompt,
        answer: completion.answer,
        approved: completion.approved,
        agent: agentId ? parseInt(agentId) : null,
      });
      toast.success(t("agent-assigned"));
      onRefresh();
    } catch {
      toast.error(t("error-assigning-agent"));
    }
  };

  const handleDelete = async () => {
    try {
      await deleteCompletion(completion.id.toString());
      toast.success(t("completion-deleted"));
      onRefresh();
    } catch {
      toast.error(t("error-deleting-completion"));
    }
  };

  return (
    <Card withBorder p="md">
      {/* Prompt */}
      {isEditing ? (
        <Textarea
          value={prompt}
          onChange={(e) => setPrompt(e.currentTarget.value)}
          placeholder={t("prompt")}
          minRows={2}
          autosize
          mb="xs"
        />
      ) : (
        <Text fw={600} mb={4}>
          {completion.prompt}
        </Text>
      )}

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
        {agentName && (
          <Badge
            size="xs"
            variant="default"
            leftSection={<IconRobot size={10} />}
          >
            {agentName}
          </Badge>
        )}
      </Group>

      {/* Answer */}
      {isEditing ? (
        <Textarea
          value={answer}
          onChange={(e) => setAnswer(e.currentTarget.value)}
          placeholder={t("answer")}
          minRows={3}
          autosize
          mb="sm"
        />
      ) : (
        <Text size="sm" c="dimmed" mb="sm" style={{ whiteSpace: "pre-wrap" }}>
          {completion.answer}
        </Text>
      )}

      {/* Actions */}
      <Group gap="xs" wrap="wrap">
        <NativeSelect
          size="xs"
          value={completion.agent?.toString() || ""}
          onChange={(e) => handleAssignAgent(e.currentTarget.value)}
          data={[
            { value: "", label: t("no-agent-assigned") },
            ...agents
              .filter((a) => a.id)
              .map((a) => ({
                value: a.id!.toString(),
                label: a.name,
              })),
          ]}
          style={{ minWidth: 140 }}
        />

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

        {isEditing ? (
          <>
            <Button size="xs" onClick={handleSave}>
              {t("save")}
            </Button>
            <Button
              variant="default"
              size="xs"
              onClick={() => {
                setIsEditing(false);
                setPrompt(completion.prompt);
                setAnswer(completion.answer);
              }}
            >
              {t("cancel")}
            </Button>
          </>
        ) : (
          <Button
            variant="default"
            size="xs"
            leftSection={<IconEdit size={14} />}
            onClick={() => setIsEditing(true)}
          >
            {t("edit")}
          </Button>
        )}

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
    </Card>
  );
};
