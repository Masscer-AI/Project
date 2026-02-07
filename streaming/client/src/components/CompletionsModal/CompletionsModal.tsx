import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import {
  bulkDeleteCompletions,
  bulkUpdateCompletions,
  deleteCompletion,
  getUserCompletions,
  updateCompletion,
} from "../../modules/apiCalls";

import { TCompletion } from "../../types";
import { SvgButton } from "../SvgButton/SvgButton";
import { useStore } from "../../modules/store";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { Checkbox } from "../Checkbox/Checkbox";
import { toast } from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Textarea } from "../SimpleForm/Textarea";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import { Loader } from "../Loader/Loader";
import { Icon } from "../Icon/Icon";

export const CompletionsModal = ({ visible, hide }) => {
  const { t } = useTranslation();
  const [completions, setCompletions] = useState([] as TCompletion[]);
  const [isLoading, setIsLoading] = useState(false);
  const [filteredCompletions, setFilteredCompletions] = useState(
    [] as TCompletion[]
  );
  const [filter, setFilter] = useState("all");
  const [completionsAgents, setCompletionsAgents] = useState([] as number[]);
  const [selectedCompletions, setSelectedCompletions] = useState(
    [] as TCompletion[]
  );
  const [hoveredFilter, setHoveredFilter] = useState<string | null>(null);
  const [hoveredAction, setHoveredAction] = useState<string | null>(null);

  useEffect(() => {
    getCompletions();
  }, []);

  const { agents } = useStore((s) => ({
    agents: s.agents,
  }));

  const getCompletions = async () => {
    const completions = await getUserCompletions();

    setCompletions(completions);
    setFilteredCompletions(completions);

    const completionsAgents = completions.map((c) => c.agent);
    const distinctAgents = [...new Set(completionsAgents)];
    setCompletionsAgents(distinctAgents);
  };

  useEffect(() => {
    applyFilter(filter);
  }, [filter, completions]);

  const applyFilter = (filter: string) => {
    if (filter === "all") {
      setFilteredCompletions(completions);
    }
    if (filter === "approved") {
      setFilteredCompletions(completions.filter((c) => c.approved));
    }
    if (filter === "pending") {
      setFilteredCompletions(completions.filter((c) => !c.approved));
    }
    if (filter.startsWith("agent-")) {
      setFilteredCompletions(
        completions.filter((c) => c.agent === parseInt(filter.split("-")[1]))
      );
    }
  };

  const updateCompletionAction = async (completionId: string, data: any) => {
    await updateCompletion(completionId, data);
    const updatedCompletions = completions.map((c) =>
      c.id.toString() === completionId ? { ...c, ...data } : c
    );
    setCompletions(updatedCompletions);
    toast.success(t("completion-updated"));
  };

  const handleDelete = async (completionId: string) => {
    await deleteCompletion(completionId);
    const filtered = completions.filter((c) => c.id !== parseInt(completionId));
    setCompletions(filtered);
    if (
      selectedCompletions.findIndex((c) => c.toString() === completionId) !== -1
    ) {
      setSelectedCompletions(
        selectedCompletions.filter((c) => c.id.toString() !== completionId)
      );
    }
    toast.success(t("completion-deleted"));
  };

  const handleSelect = (c: TCompletion) => {
    if (
      selectedCompletions.findIndex(
        (com) => com.id.toString() === c.id.toString()
      ) !== -1
    ) {
      setSelectedCompletions(
        selectedCompletions.filter(
          (com) => com.id.toString() !== c.id.toString()
        )
      );
      return;
    }
    setSelectedCompletions([...selectedCompletions, c]);
  };

  const handleBulkUpdate = async () => {
    await bulkUpdateCompletions(selectedCompletions);

    setCompletions((prev) => {
      return prev.map((c) => {
        if (selectedCompletions.findIndex((com) => com.id === c.id) !== -1) {
          return { ...c, approved: true };
        }
        return c;
      });
    });
    setSelectedCompletions([]);
    toast.success(t("completions-approved"));
  };

  const bulkDelete = async () => {
    bulkDeleteCompletions(selectedCompletions);
    setCompletions(
      completions.filter(
        (c) => selectedCompletions.findIndex((com) => com.id === c.id) === -1
      )
    );
    setSelectedCompletions([]);
    toast.success(t("completions-deleted"));
  };

  return (
    <Modal minHeight={"80dvh"} visible={visible} hide={hide}>
      <div className="flex flex-col gap-5">
        <h3 className="text-center p-1.5">
          {t("completions-pending-for-approval")}
        </h3>
        <div className="items-center flex flex-col gap-1.5 p-1.5 flex-wrap">
          <span>{t("filter-by")}: </span>
          <div className="overflow-x-auto scrollbar-none flex justify-center gap-2 flex-wrap">
            <button
              className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                hoveredFilter === 'all' || filter === "all"
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredFilter('all')}
              onMouseLeave={() => setHoveredFilter(null)}
              onClick={() => setFilter("all")}
            >
              {t("all")}
            </button>
            <button
              className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                hoveredFilter === 'approved' || filter === "approved"
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredFilter('approved')}
              onMouseLeave={() => setHoveredFilter(null)}
              onClick={() => setFilter("approved")}
            >
              {t("approved")}
            </button>
            <button
              className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                hoveredFilter === 'pending' || filter === "pending"
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredFilter('pending')}
              onMouseLeave={() => setHoveredFilter(null)}
              onClick={() => setFilter("pending")}
            >
              {t("pending")}
            </button>
            {completionsAgents.map((a) => (
              <button
                key={a}
                className={`px-6 py-2 rounded-full font-normal text-sm cursor-pointer border ${
                  hoveredFilter === `agent-${a}` || filter === `agent-${a}`
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onMouseEnter={() => setHoveredFilter(`agent-${a}`)}
                onMouseLeave={() => setHoveredFilter(null)}
                onClick={() => setFilter(`agent-${a}`)}
              >
                {agents.find((ag) => ag.id === a)?.name}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2.5">
            <div>
              {selectedCompletions.length} {t("selected")}
            </div>
            <FloatingDropdown
              right="0"
              top="100%"
              extraClass="mt-2"
              opener={
                <SvgButton
                  extraClass="active-on-hover "
                  text={t("group-actions")}
                  svg={<Icon name="MoreVertical" size={20} />}
                />
              }
            >
              <div className="w-[200px] flex flex-col gap-3 p-4 bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl shadow-lg">
                <button
                  className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
                    hoveredAction === 'delete-all' 
                      ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                      : 'bg-[rgba(220,38,38,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(220,38,38,0.8)]'
                  }`}
                  style={{ transform: 'none' }}
                  onMouseEnter={() => setHoveredAction('delete-all')}
                  onMouseLeave={() => setHoveredAction(null)}
                  onClick={() => {
                    if (window.confirm(t("sure-delete-completions"))) {
                      bulkDelete();
                    }
                  }}
                >
                  <span>{t("delete-all")}</span>
                </button>
                <button
                  className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
                    hoveredAction === 'approve-all' 
                      ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                      : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                  }`}
                  style={{ transform: 'none' }}
                  onMouseEnter={() => setHoveredAction('approve-all')}
                  onMouseLeave={() => setHoveredAction(null)}
                  onClick={handleBulkUpdate}
                >
                  <span>{t("approve-all")}</span>
                </button>
              </div>
            </FloatingDropdown>
          </div>
        </div>

        <div className="flex flex-wrap gap-[10px] justify-center p-[10px] overflow-auto max-h-[60dvh]">
          {isLoading && <Loader />}
          {filteredCompletions.map((c) => (
            <CompletionCard
              handleSelect={handleSelect}
              updateCompletion={updateCompletionAction}
              key={c.id}
              handleDelete={handleDelete}
              completion={c}
              selected={
                selectedCompletions.findIndex((com) => com.id == c.id) !== -1
              }
            />
          ))}
        </div>
      </div>
    </Modal>
  );
};

type CompletionCardProps = {
  completion: TCompletion;
  updateCompletion: (completionId: string, data: any) => void;
  handleSelect: (c: TCompletion) => void;
  handleDelete: (completionId: string) => void;
  selected: boolean;
};

const CompletionCard = ({
  completion,
  updateCompletion,
  handleSelect,
  selected,
  handleDelete,
}: CompletionCardProps) => {
  const { t } = useTranslation();

  const [isEditing, setIsEditing] = useState(false);
  const [answer, setAnswer] = useState(completion.answer);
  const [prompt, setPrompt] = useState(completion.prompt);

  const toggleEdit = () => {
    if (isEditing) {
      saveCompletion();
    }
    setIsEditing(!isEditing);
  };

  const saveCompletion = async () => {
    updateCompletion(completion.id.toString(), {
      answer: answer,
      prompt: prompt,
      approved: completion.approved,
    });
    setIsEditing(false);
  };

  const handleAnswerChange = (value) => {
    setAnswer(value);
  };

  const handlePromptChange = (e) => {
    setPrompt(e.target.value);
  };

  const handleApprovedChange = (e) => {
    updateCompletion(completion.id.toString(), {
      answer: answer,
      prompt: prompt,
      approved: e.target.checked,
    });
  };

  return (
    <div className={`rounded-[10px] p-2.5 bg-[var(--code-bg-color)] cursor-pointer flex flex-col gap-2.5 w-[min(350px,100%)] transition-all duration-200 ease-in-out mx-auto border-4 ${selected ? "border-[var(--active-color)]" : "border-[var(--semi-transparent)]"}`}>
      <section
        onClick={() => handleSelect(completion)}
        className="flex flex-col gap-2.5"
      >
        {isEditing ? (
          <input
            className="rounded-lg p-5 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] text-base font-[var(--font-family)] text-[var(--font-color)] transition-all duration-200 focus:outline-none focus:border-[rgba(255,255,255,0.2)] focus:shadow-[0_0_0_2px_rgba(110,91,255,0.3)]"
            onChange={handlePromptChange}
            value={prompt}
          />
        ) : (
          <h4>{prompt}</h4>
        )}
        <div className="border-t border-[var(--active-color)] opacity-10 w-full" />
        {isEditing ? (
          <Textarea
            extraClass=""
            name="answer"
            label={t("this-is-how-the-ai-supposed-to-answer")}
            defaultValue={answer}
            onChange={handleAnswerChange}
          />
        ) : (
          <MarkdownRenderer markdown={answer} />
        )}
      </section>
      <div className="flex gap-1.5 justify-center items-center">
        <Checkbox
          checked={completion.approved}
          onChange={handleApprovedChange}
          checkedFill="var(--success-color)"
        />
        <SvgButton
          onClick={toggleEdit}
          text={isEditing ? t("finish") : t("edit")}
          extraClass={
            isEditing ? "bg-hovered active-on-hover pressable" : "pressable"
          }
          svg={isEditing ? <Icon name="Check" size={20} /> : <Icon name="PenLine" size={20} />}
        />
        <SvgButton
          confirmations={["Sure?"]}
          title={t("delete")}
          extraClass=" danger-on-hover pressable"
          svg={<Icon name="Trash2" size={20} />}
          onClick={() => handleDelete(completion.id.toString())}
        />
      </div>
    </div>
  );
};
