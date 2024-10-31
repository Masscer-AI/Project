import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import {
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

export const CompletionsModal = ({ visible, hide }) => {
  const { t } = useTranslation();
  const [completions, setCompletions] = useState([] as TCompletion[]);
  const [filteredCompletions, setFilteredCompletions] = useState(
    [] as TCompletion[]
  );
  const [filter, setFilter] = useState("all");
  const [completionsAgents, setCompletionsAgents] = useState([] as number[]);

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
  }, [filter]);

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
    toast.success(t("completion-updated"));
  };

  const handleDelete = async (completionId: string) => {
    await deleteCompletion(completionId);
    const filtered = completions.filter((c) => c.id !== parseInt(completionId));
    setCompletions(filtered);
    applyFilter(filter);
    toast.success(t("completion-deleted"));
  };

  return (
    <Modal visible={visible} hide={hide}>
      <h3 className="text-center">{t("completions-pending-for-approval")}</h3>
      <div className="d-flex align-center gap-small padding-medium">
        <span>{t("filter-by")}: </span>
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
      <p className="text-center">
        {t(
          "a-completion-is-a-pair-of-a-prompt-and-an-answer-you-can-use-this-page-to-train-your-model-with-completions"
        )}
      </p>
      <div className="d-flex flex-y gap-big">
        {filteredCompletions.map((c) => (
          <CompletionCard
            deleteCompletion={handleDelete}
            updateCompletion={updateCompletionAction}
            key={c.id}
            completion={c}
          />
        ))}
      </div>
    </Modal>
  );
};

type CompletionCardProps = {
  completion: TCompletion;
  updateCompletion: (completionId: string, data: any) => void;
  deleteCompletion: (completionId: string) => void;
};

const CompletionCard = ({
  completion,
  updateCompletion,
  deleteCompletion,
}: CompletionCardProps) => {
  const { t } = useTranslation();

  const [isEditing, setIsEditing] = useState(false);
  const [answer, setAnswer] = useState(completion.answer);
  const [prompt, setPrompt] = useState(completion.prompt);
  const [approved, setApproved] = useState(completion.approved);

  const toggleEdit = () => {
    setIsEditing(!isEditing);
  };

  const saveCompletion = async () => {
    updateCompletion(completion.id.toString(), {
      answer: answer,
      prompt: prompt,
      approved: approved,
    });
    setIsEditing(false);
  };

  const handleAnswerChange = (e) => {
    setAnswer(e.target.value);
  };

  const handlePromptChange = (e) => {
    setPrompt(e.target.value);
  };

  const handleApprovedChange = (e) => {
    setApproved(e.target.checked);
  };

  const toggleApproved = () => {
    setApproved(!approved);
  };

  return (
    <div className={styles.completionCard}>
      {isEditing ? (
        <input onChange={handlePromptChange} value={prompt} />
      ) : (
        <h4>{prompt}</h4>
      )}
      {isEditing ? (
        <textarea onChange={handleAnswerChange} value={answer} />
      ) : (
        <MarkdownRenderer markdown={answer} />
      )}
      <div className="d-flex gap-small justify-center align-center">
        <Checkbox checked={approved} onChange={handleApprovedChange} />
        <SvgButton
          onClick={toggleApproved}
          text={approved ? t("unapprove") : t("approve")}
          svg={approved ? SVGS.close : SVGS.plus}
        />
        <SvgButton
          onClick={toggleEdit}
          text={isEditing ? t("finish") : t("edit")}
          extraClass={isEditing ? "bg-active" : ""}
          svg={isEditing ? SVGS.finish : SVGS.writePen}
        />
        <SvgButton
          confirmations={["Sure?"]}
          title={t("delete")}
          svg={SVGS.trash}
          onClick={() => deleteCompletion(completion.id.toString())}
        />
        <SvgButton
          onClick={saveCompletion}
          text={t("save-in-memory")}
          svg={SVGS.save}
        />
        <Pill extraClass="bg-hovered">Agent: {completion.agent}</Pill>
      </div>
    </div>
  );
};
