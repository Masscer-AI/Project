import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import {
  generateTrainingCompletions,
  getDocuments,
} from "../../modules/apiCalls";
import styles from "./DocumentsModal.module.css";

import { useTranslation } from "react-i18next";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { Pill } from "../Pill/Pill";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";
type TDocument = {
  id: number;
  name: string;
  brief: string;
  chunk_count: number;
  chunk_set: any[];
};

export const DocumentsModal = ({ visible, hide }) => {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState([] as TDocument[]);

  useEffect(() => {
    getDocs();
  }, []);

  const getDocs = async () => {
    const docs = await getDocuments();
    setDocuments(docs); // Store the documents in state
    console.log(docs);
  };

  return (
    <Modal visible={visible} hide={hide} minHeight="80vh">
      <h3 className="text-center">{t("knowledge-base")}</h3>
      <p className="text-center">
        {t("you-can-use-this-page-to-train-your-model-with-files")}
      </p>
      <div>
        {documents.map((document) => (
          <DocumentCard key={document.id} document={document} />
        ))}
      </div>
    </Modal>
  );
};

const DocumentCard = ({ document }) => {
  const [isOpened, setIsOpened] = useState(false);
  const [displayBrief, setDisplayBrief] = useState(false);
  const [isTrainingModalVisible, setIsTrainingModalVisible] = useState(false);
  const [search, setSearch] = useState("");
  const [filteredChunks, setFilteredChunks] = useState(document.chunk_set);
  const { t } = useTranslation();

  useEffect(() => {
    setFilteredChunks(
      document.chunk_set.filter((c) =>
        c.content.toLowerCase().includes(search.toLowerCase())
      )
    );
  }, [search]);

  return (
    <div className={styles.documentCard}>
      {isTrainingModalVisible && (
        <TrainingOnDocument
          hide={() => setIsTrainingModalVisible(false)}
          document={document}
        />
      )}
      <h3 className="text-center">
        <p>{document.name}</p>
      </h3>
      <div className="d-flex justify-center gap-small">
        <Pill extraClass="bg-hovered">{document.chunk_count} chunks</Pill>
        <Pill extraClass="bg-hovered">{document.collection.agent.name}</Pill>
        <Pill
          extraClass="bg-active"
          onClick={() => setDisplayBrief(!displayBrief)}
        >
          {displayBrief ? t("hide-brief") : t("show-brief")}
        </Pill>
        <Pill extraClass="bg-hovered">{document.total_tokens} tokens</Pill>
      </div>
      {displayBrief && <p>{document.brief}</p>}

      <div className="d-flex justify-center gap-small">
        <SvgButton
          extraClass="bg-hovered"
          text={isOpened ? t("hide-document-text") : t("show-document-text")}
          onClick={() => setIsOpened(!isOpened)}
        />
        <SvgButton
          extraClass="bg-active"
          text={t("train-on-this-document")}
          onClick={() => setIsTrainingModalVisible(true)}
        />
        
      </div>
      {isOpened && (
        <>
          <div className="d-flex justify-center">
            <input
              type="text"
              className="input"
              placeholder={t("find-something-in-the-document")}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className={styles.chunkContainer}>
            {filteredChunks.map((c) => (
              <Chunk key={c.id} content={c.content} id={c.id} />
            ))}
          </div>
        </>
      )}
    </div>
  );
};

const Chunk = ({ content, id }) => {
  const [displayFull, setDisplayFull] = useState(false);

  return (
    <pre
      title={`This chunk is text is from the chunk ${id.toString()}`}
      onClick={() => setDisplayFull(!displayFull)}
    >
      {displayFull ? content : content.slice(0, 100)}
    </pre>
  );
};

const TrainingOnDocument = ({
  hide,
  document,
}: {
  hide: () => void;
  document: TDocument;
}) => {
  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
  };

  const { agents } = useStore((state) => ({
    agents: state.agents,
  }));

  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [completionsTargetNumber, setCompletionsTargetNumber] = useState(30);
  const toggleAgent = (slug: string) => {
    if (selectedAgents.includes(slug)) {
      setSelectedAgents((prev) => prev.filter((s) => s !== slug));
    } else {
      setSelectedAgents((prev) => [...prev, slug]);
    }
  };

  const generateTrainingData = async () => {
    if (selectedAgents.length === 0) {
      toast.error("Please select at least one agent");
    }

    const res = await generateTrainingCompletions({
      model_id: document.id.toString(),
      db_model: "document",
      agents: selectedAgents,
      completions_target_number: completionsTargetNumber,
    });
    toast.success("Training generation in queue...");
    hide();
  };

  return (
    <Modal hide={hide} minHeight="80vh">
      <div className="d-flex flex-y gap-big">
        <h2 className="text-center">Generate completions</h2>
        <p>
          If you think the document <strong>{document.name}</strong> is relevant
          to your business, you can generate completions for it to add more
          context to your agents when answering similar conversations in the
          future.
        </p>
        <p>
          After generating completions, you can approve, edit or discard them.
        </p>
        <form onSubmit={onSubmit} action="">
          <label>
            Number of completions to generate
            <input
              className="input"
              type="number"
              defaultValue={30}
              onChange={(e) =>
                setCompletionsTargetNumber(parseInt(e.target.value))
              }
            />
          </label>
          <p>
            Select the agents that will retrain on this conversation. Keep in
            mind that each agent will generate its own completions based on its
            system prompt.
          </p>
          <div className="d-flex gap-small wrap-wrap padding-medium">
            {agents.map((a) => (
              <Pill
                extraClass={`${selectedAgents.includes(a.slug) ? "bg-active" : "bg-hovered"}`}
                key={a.id}
                onClick={() => toggleAgent(a.slug)}
              >
                {a.name}
              </Pill>
            ))}
          </div>
        </form>
        <SvgButton
          svg={SVGS.dumbell}
          text="Generate"
          size="big"
          onClick={generateTrainingData}
        />
      </div>
    </Modal>
  );
};
