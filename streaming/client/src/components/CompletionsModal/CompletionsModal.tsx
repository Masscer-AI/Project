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
import { SVGS } from "../../assets/svgs";
import { Pill } from "../Pill/Pill";
import { useStore } from "../../modules/store";
import styles from "./CompletionsModal.module.css";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { Checkbox } from "../Checkbox/Checkbox";
import { toast } from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Textarea } from "../SimpleForm/Textarea";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import { Loader } from "../Loader/Loader";

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
    // toast.success("Bulk update");
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
      <div className="flex-y gap-big">
        <h3 className="text-center padding-small">
          {t("completions-pending-for-approval")}
        </h3>
        <div className=" align-center flex-y gap-small padding-small wrap-wrap">
          <span>{t("filter-by")}: </span>
          <div className="overflow-x-auto no-scrollbar d-flex justify-center">
            <Pill
              onClick={() => setFilter("all")}
              extraClass={filter === "all" ? "bg-active" : ""}
            >
              {t("all")}
            </Pill>
            <Pill
              onClick={() => setFilter("approved")}
              extraClass={filter === "approved" ? "bg-active" : ""}
            >
              {t("approved")}
            </Pill>

            <Pill
              onClick={() => setFilter("pending")}
              extraClass={filter === "pending" ? "bg-active" : ""}
            >
              {t("pending")}
            </Pill>
            {completionsAgents.map((a) => (
              <Pill
                onClick={() => setFilter(`agent-${a}`)}
                extraClass={filter === `agent-${a}` ? "bg-active" : ""}
                key={a}
              >
                {agents.find((ag) => ag.id === a)?.name}
              </Pill>
            ))}
          </div>

          <div className="d-flex align-center gap-medium">
            <div>
              {selectedCompletions.length} {t("selected")}
            </div>
            <FloatingDropdown
              left="50%"
              top="100%"
              transform="translateX(-50%)"
              opener={
                <SvgButton
                  extraClass="active-on-hover "
                  text={t("group-actions")}
                  svg={SVGS.options}
                />
              }
            >
              <div className="width-200 flex-y gap-medium">
                <SvgButton
                  extraClass=" pressable bg-danger"
                  size="big"
                  text={t("delete-all")}
                  onClick={bulkDelete}
                  confirmations={[t("sure-delete-completions")]}
                />
                <SvgButton
                  onClick={handleBulkUpdate}
                  extraClass=" bg-active pressable"
                  size="big"
                  text={t("approve-all")}
                />
              </div>
            </FloatingDropdown>
          </div>
        </div>

        <div className={styles.completionsContainer}>
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
    // setApproved(e.target.checked);
    updateCompletion(completion.id.toString(), {
      answer: answer,
      prompt: prompt,
      approved: e.target.checked,
    });
  };

  return (
    <div className={`card fat-border ${selected ? " border-active " : ""}`}>
      <section
        onClick={() => handleSelect(completion)}
        className="flex-y gap-medium"
      >
        {isEditing ? (
          <input
            className="input padding-big"
            onChange={handlePromptChange}
            value={prompt}
          />
        ) : (
          <h4>{prompt}</h4>
        )}
        <div className={`separator checked `} />
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
      <div className="d-flex gap-small justify-center align-center">
        {/* <SvgButton
          onClick={toggleApproved}
          text={selected ? t("unselect") : t("select")}
        /> */}
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
          svg={isEditing ? SVGS.finish : SVGS.writePen}
        />
        <SvgButton
          confirmations={["Sure?"]}
          title={t("delete")}
          extraClass=" danger-on-hover pressable"
          svg={SVGS.trash}
          onClick={() => handleDelete(completion.id.toString())}
        />
        {/* <Pill extraClass="bg-hovered">Agent: {completion.agent}</Pill> */}
      </div>
    </div>
  );
};
