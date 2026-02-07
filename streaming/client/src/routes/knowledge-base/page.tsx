import React, { useState, useEffect, useRef } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  getDocuments,
  uploadDocument,
  deleteDocument,
  generateDocumentBrief,
  getUserCompletions,
  updateCompletion,
  deleteCompletion,
  createCompletion,
} from "../../modules/apiCalls";
import { TDocument, TCompletion } from "../../types";
import { useTranslation } from "react-i18next";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import toast from "react-hot-toast";
import { Icon } from "../../components/Icon/Icon";
import { Loader } from "../../components/Loader/Loader";
import { TAgent } from "../../types/agents";
import "./page.css";

type TabType = "documents" | "completions";

export default function KnowledgeBasePage() {
  const { chatState, toggleSidebar, agents, fetchAgents } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabType>("documents");
  const [documents, setDocuments] = useState<TDocument[]>([]);
  const [completions, setCompletions] = useState<TCompletion[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingCompletions, setLoadingCompletions] = useState(true);
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState<string>("all");

  useEffect(() => {
    loadDocuments();
    loadCompletions();
    // Load agents if not already loaded
    if (agents.length === 0) {
      fetchAgents();
    }
  }, []);

  const loadDocuments = async () => {
    setLoadingDocs(true);
    try {
      const docs = await getDocuments();
      setDocuments(docs);
    } catch {
      toast.error(t("error-loading-documents"));
    } finally {
      setLoadingDocs(false);
    }
  };

  const loadCompletions = async () => {
    setLoadingCompletions(true);
    try {
      const comps = await getUserCompletions();
      setCompletions(comps);
    } catch {
      toast.error(t("error-loading-completions"));
    } finally {
      setLoadingCompletions(false);
    }
  };

  const filteredDocuments = documents.filter((doc) =>
    doc.name?.toLowerCase().includes(search.toLowerCase()) ||
    doc.brief?.toLowerCase().includes(search.toLowerCase())
  );

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
      <div className="kb-container relative">
        {!chatState.isSidebarOpened && (
          <div className="absolute top-6 left-6 z-10">
            <SvgButton
              extraClass="pressable active-on-hover"
              onClick={toggleSidebar}
              svg={<Icon name="Menu" size={20} />}
            />
          </div>
        )}
        <div className="max-w-4xl mx-auto px-4">
          <div className="kb-header">
            <h1 className="text-2xl md:text-4xl font-bold mb-4 md:mb-8 text-center text-white tracking-tight">
              {t("knowledge-base")}
            </h1>
            <p className="text-center text-[rgb(156,156,156)] mb-6">
              {t("knowledge-base-description")}
            </p>
          </div>

          {/* Tabs */}
          <div className="kb-tabs">
            <button
              className={`kb-tab ${activeTab === "documents" ? "active" : ""}`}
              onClick={() => setActiveTab("documents")}
            >
              <span className="flex items-center gap-2">
                <Icon name="FileText" size={16} />
                {t("documents")} ({documents.length})
              </span>
            </button>
            <button
              className={`kb-tab ${activeTab === "completions" ? "active" : ""}`}
              onClick={() => setActiveTab("completions")}
            >
              <span className="flex items-center gap-2">
                <Icon name="Sparkles" size={16} />
                {t("completions")} ({completions.length})
              </span>
            </button>
          </div>

          {/* Filter Row */}
          <div className="kb-filter-row">
            <input
              type="text"
              className="kb-search-input"
              placeholder={t("search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {activeTab === "completions" && (
              <select
                className="kb-agent-select"
                value={agentFilter}
                onChange={(e) => setAgentFilter(e.target.value)}
              >
                <option value="all">{t("all-agents")}</option>
                {agents.filter(a => a.id).map((agent) => (
                  <option key={agent.id} value={agent.id!.toString()}>
                    {agent.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Content */}
          <div className="kb-content">
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
          </div>
        </div>
      </div>
    </main>
  );
}

// Documents Tab Component
type DocumentsTabProps = {
  documents: TDocument[];
  loading: boolean;
  onRefresh: () => void;
  agents: TAgent[];
};

const DocumentsTab = ({ documents, loading, onRefresh, agents }: DocumentsTabProps) => {
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
        const formData = new FormData();
        formData.append("file", file);
        await uploadDocument(formData);
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
    if (!window.confirm(t("sure") + "?")) return;

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

  const handleGenerateBrief = async (docId: number) => {
    const toastId = toast.loading(t("generating-brief"));
    try {
      await generateDocumentBrief(docId.toString());
      toast.success(t("brief-generated"));
      onRefresh();
    } catch {
      toast.error(t("error-generating-brief"));
    } finally {
      toast.dismiss(toastId);
    }
  };

  if (loading) {
    return <Loader text={t("loading-documents")} />;
  }

  return (
    <div>
      {/* Upload Area */}
      <div
        className={`kb-upload-area ${dragging ? "dragging" : ""}`}
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
          className="hidden"
          onChange={(e) => handleFileUpload(e.target.files)}
        />
        <Icon name="Upload" size={32} className="mx-auto mb-3 text-[rgb(156,156,156)]" />
        <p className="text-[rgb(156,156,156)] m-0">
          {uploading ? t("uploading") + "..." : t("drag-drop-or-click-to-upload")}
        </p>
      </div>

      {/* Documents List */}
      {documents.length === 0 ? (
        <div className="kb-empty">
          <p>{t("no-documents-yet")}</p>
        </div>
      ) : (
        documents.map((doc) => (
          <DocumentItem
            key={doc.id}
            document={doc}
            agents={agents}
            onDelete={() => handleDelete(doc.id)}
            onGenerateBrief={() => handleGenerateBrief(doc.id)}
          />
        ))
      )}
    </div>
  );
};

type DocumentItemProps = {
  document: TDocument;
  agents: TAgent[];
  onDelete: () => void;
  onGenerateBrief: () => void;
};

const DocumentItem = ({ document, agents, onDelete, onGenerateBrief }: DocumentItemProps) => {
  const { t } = useTranslation();
  const [hoveredAction, setHoveredAction] = useState<string | null>(null);

  return (
    <div className="kb-item">
      <div className="kb-item-header">
        <h3 className="kb-item-title">{document.name || t("untitled")}</h3>
      </div>
      <div className="kb-item-meta">
        <span className="kb-pill">
          <Icon name="FileText" size={12} />
          {document.chunk_count} {t("chunks")}
        </span>
        <span className="kb-pill">
          <Icon name="Hash" size={12} />
          {document.total_tokens} {t("tokens")}
        </span>
      </div>
      {document.brief && (
        <p className="kb-item-brief">{document.brief}</p>
      )}
      <div className="kb-item-actions">
        {!document.brief && (
          <button
            className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
              hoveredAction === "brief"
                ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
            }`}
            onMouseEnter={() => setHoveredAction("brief")}
            onMouseLeave={() => setHoveredAction(null)}
            onClick={onGenerateBrief}
          >
            <Icon name="Sparkles" size={14} />
            {t("generate-brief")}
          </button>
        )}
        <button
          className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
            hoveredAction === "delete"
              ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
              : "bg-[rgba(220,38,38,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(220,38,38,0.8)]"
          }`}
          onMouseEnter={() => setHoveredAction("delete")}
          onMouseLeave={() => setHoveredAction(null)}
          onClick={onDelete}
        >
          <Icon name="Trash2" size={14} />
          {t("delete")}
        </button>
      </div>
    </div>
  );
};

// Completions Tab Component
type CompletionsTabProps = {
  completions: TCompletion[];
  loading: boolean;
  onRefresh: () => void;
  agents: TAgent[];
};

const CompletionsTab = ({ completions, loading, onRefresh, agents }: CompletionsTabProps) => {
  const { t } = useTranslation();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newPrompt, setNewPrompt] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [newAgentId, setNewAgentId] = useState<string>("");
  const [creating, setCreating] = useState(false);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!newPrompt.trim() || !newAnswer.trim()) {
      toast.error(t("prompt-and-answer-required"));
      return;
    }

    setCreating(true);
    const toastId = toast.loading(t("creating"));
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
      setShowCreateForm(false);
      onRefresh();
    } catch {
      toast.error(t("error-creating-completion"));
    } finally {
      toast.dismiss(toastId);
      setCreating(false);
    }
  };

  if (loading) {
    return <Loader text={t("loading-completions")} />;
  }

  return (
    <div>
      {/* Create Button */}
      {!showCreateForm && (
        <div className="mb-4">
          <button
            className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 ${
              hoveredButton === "new"
                ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
            }`}
            onMouseEnter={() => setHoveredButton("new")}
            onMouseLeave={() => setHoveredButton(null)}
            onClick={() => setShowCreateForm(true)}
          >
            <Icon name="Plus" size={18} />
            {t("new-completion")}
          </button>
        </div>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="kb-completion-form">
          <h3 className="text-white font-semibold m-0">{t("create-completion")}</h3>
          <div className="flex flex-col gap-2">
            <label className="text-[rgb(156,156,156)] text-sm">{t("prompt")}</label>
            <textarea
              value={newPrompt}
              onChange={(e) => setNewPrompt(e.target.value)}
              placeholder={t("prompt-placeholder")}
              rows={2}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-[rgb(156,156,156)] text-sm">{t("answer")}</label>
            <textarea
              value={newAnswer}
              onChange={(e) => setNewAnswer(e.target.value)}
              placeholder={t("answer-placeholder")}
              rows={4}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-[rgb(156,156,156)] text-sm">{t("assign-to-agent")}</label>
            <select
              className="kb-agent-select"
              value={newAgentId}
              onChange={(e) => setNewAgentId(e.target.value)}
            >
              <option value="">{t("no-agent-assigned")}</option>
              {agents.filter(a => a.id).map((agent) => (
                <option key={agent.id} value={agent.id!.toString()}>
                  {agent.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={creating}
              className={`flex-1 px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center gap-2 ${
                hoveredButton === "create"
                  ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                  : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
              }`}
              onMouseEnter={() => setHoveredButton("create")}
              onMouseLeave={() => setHoveredButton(null)}
            >
              <Icon name="Save" size={16} />
              {t("create")}
            </button>
            <button
              onClick={() => {
                setShowCreateForm(false);
                setNewPrompt("");
                setNewAnswer("");
                setNewAgentId("");
              }}
              className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center justify-center ${
                hoveredButton === "cancel"
                  ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                  : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
              }`}
              onMouseEnter={() => setHoveredButton("cancel")}
              onMouseLeave={() => setHoveredButton(null)}
            >
              {t("cancel")}
            </button>
          </div>
        </div>
      )}

      {/* Completions List */}
      {completions.length === 0 && !showCreateForm ? (
        <div className="kb-empty">
          <p>{t("no-completions-yet")}</p>
          <p className="text-sm mt-2">{t("completions-hint")}</p>
        </div>
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
    </div>
  );
};

type CompletionItemProps = {
  completion: TCompletion;
  agents: TAgent[];
  onRefresh: () => void;
};

const CompletionItem = ({ completion, agents, onRefresh }: CompletionItemProps) => {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [prompt, setPrompt] = useState(completion.prompt);
  const [answer, setAnswer] = useState(completion.answer);
  const [hoveredAction, setHoveredAction] = useState<string | null>(null);

  const agentName = agents.find((a) => a.id === completion.agent)?.name;

  const handleSave = async () => {
    const toastId = toast.loading(t("saving"));
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
    } finally {
      toast.dismiss(toastId);
    }
  };

  const handleApprove = async () => {
    const toastId = toast.loading(t("saving"));
    try {
      await updateCompletion(completion.id.toString(), {
        prompt: completion.prompt,
        answer: completion.answer,
        approved: !completion.approved,
      });
      toast.success(completion.approved ? t("completion-unapproved") : t("completion-approved"));
      onRefresh();
    } catch {
      toast.error(t("error-updating-completion"));
    } finally {
      toast.dismiss(toastId);
    }
  };

  const handleAssignAgent = async (agentId: string) => {
    const toastId = toast.loading(t("saving"));
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
    } finally {
      toast.dismiss(toastId);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(t("sure") + "?")) return;

    const toastId = toast.loading(t("deleting"));
    try {
      await deleteCompletion(completion.id.toString());
      toast.success(t("completion-deleted"));
      onRefresh();
    } catch {
      toast.error(t("error-deleting-completion"));
    } finally {
      toast.dismiss(toastId);
    }
  };

  return (
    <div className="kb-item">
      <div className="kb-item-header">
        <div className="flex-1">
          {isEditing ? (
            <textarea
              className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)] resize-none mb-2"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={t("prompt")}
              rows={2}
            />
          ) : (
            <h3 className="kb-item-title">{completion.prompt}</h3>
          )}
        </div>
      </div>

      <div className="kb-item-meta">
        <span className={`kb-pill ${completion.approved ? "bg-green-500/20 text-green-400" : "bg-yellow-500/20 text-yellow-400"}`}>
          <Icon name={completion.approved ? "Check" : "Clock"} size={12} />
          {completion.approved ? t("approved") : t("pending")}
        </span>
        {agentName && (
          <span className="kb-pill">
            <Icon name="Bot" size={12} />
            {agentName}
          </span>
        )}
      </div>

      {isEditing ? (
        <textarea
          className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)] resize-none mb-3"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder={t("answer")}
          rows={4}
        />
      ) : (
        <p className="kb-item-brief">{completion.answer}</p>
      )}

      <div className="kb-item-actions">
        {/* Agent assignment */}
        <select
          className="kb-agent-select"
          value={completion.agent?.toString() || ""}
          onChange={(e) => handleAssignAgent(e.target.value)}
        >
          <option value="">{t("no-agent-assigned")}</option>
          {agents.filter(a => a.id).map((agent) => (
            <option key={agent.id} value={agent.id!.toString()}>
              {agent.name}
            </option>
          ))}
        </select>

        {/* Approve/Unapprove */}
        <button
          className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
            hoveredAction === "approve"
              ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
              : completion.approved
              ? "bg-[rgba(34,197,94,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(34,197,94,0.8)]"
              : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
          }`}
          onMouseEnter={() => setHoveredAction("approve")}
          onMouseLeave={() => setHoveredAction(null)}
          onClick={handleApprove}
        >
          <Icon name={completion.approved ? "X" : "Check"} size={14} />
          {completion.approved ? t("unapprove") : t("approve")}
        </button>

        {/* Edit/Save */}
        {isEditing ? (
          <>
            <button
              className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
                hoveredAction === "save"
                  ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                  : "bg-[#6e5bff] text-white border-[rgba(156,156,156,0.3)] hover:bg-[#5a47e6]"
              }`}
              onMouseEnter={() => setHoveredAction("save")}
              onMouseLeave={() => setHoveredAction(null)}
              onClick={handleSave}
            >
              <Icon name="Save" size={14} />
              {t("save")}
            </button>
            <button
              className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
                hoveredAction === "cancel"
                  ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                  : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
              }`}
              onMouseEnter={() => setHoveredAction("cancel")}
              onMouseLeave={() => setHoveredAction(null)}
              onClick={() => {
                setIsEditing(false);
                setPrompt(completion.prompt);
                setAnswer(completion.answer);
              }}
            >
              {t("cancel")}
            </button>
          </>
        ) : (
          <button
            className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
              hoveredAction === "edit"
                ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
                : "bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]"
            }`}
            onMouseEnter={() => setHoveredAction("edit")}
            onMouseLeave={() => setHoveredAction(null)}
            onClick={() => setIsEditing(true)}
          >
            <Icon name="PenLine" size={14} />
            {t("edit")}
          </button>
        )}

        {/* Delete */}
        <button
          className={`px-4 py-2 rounded-full text-sm cursor-pointer border flex items-center gap-2 ${
            hoveredAction === "delete"
              ? "bg-white text-gray-800 border-[rgba(156,156,156,0.3)]"
              : "bg-[rgba(220,38,38,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(220,38,38,0.8)]"
          }`}
          onMouseEnter={() => setHoveredAction("delete")}
          onMouseLeave={() => setHoveredAction(null)}
          onClick={handleDelete}
        >
          <Icon name="Trash2" size={14} />
          {t("delete")}
        </button>
      </div>
    </div>
  );
};
