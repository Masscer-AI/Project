import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import {
  deleteDocument,
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
import { FloatingDropdown } from "../Dropdown/Dropdown";
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
    setDocuments(docs);
  };

  const removeDoc = (id: number) => {
    setDocuments(documents.filter((d) => d.id !== id));
  };

  return (
    <Modal visible={visible} hide={hide} minHeight="90vh">
      <div className="d-flex flex-y gap-big">
        <h3 className="text-center fancy-bg padding-big rounded F">
          {t("knowledge-base")}
        </h3>

        <p className="text-center">
          {t("you-can-use-this-page-to-train-your-model-with-files")}
        </p>
        {documents.map((document) => (
          <DocumentCard
            removeDoc={removeDoc}
            key={document.id}
            document={document}
          />
        ))}
      </div>
    </Modal>
  );
};

const DocumentCard = ({ document, removeDoc }) => {
  const [isOpened, setIsOpened] = useState(false);
  // const [displayBrief, setDisplayBrief] = useState(false);
  const [isTrainingModalVisible, setIsTrainingModalVisible] = useState(false);

  const { t } = useTranslation();

  const handleDelete = async () => {
    const tID = toast.loading("Deleting document...");
    try {
      await deleteDocument(document.id);
      toast.success("Document deleted");
      removeDoc(document.id);
    } catch (e) {
      toast.error("Error deleting document");
    }
    toast.dismiss(tID);
  };
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
        <Pill extraClass="bg-hovered">{document.total_tokens} tokens</Pill>
      </div>

      <p>{document.brief}</p>
      <div className="d-flex justify-center gap-small">
        <FloatingDropdown
          bottom="100%"
          opener={<SvgButton text={t("options")} svg={SVGS.burger} />}
        >
          <div className="width-200 d-flex flex-y gap-small">
            <SvgButton
              extraClass="bg-hovered w-100"
              text={
                isOpened ? t("hide-document-text") : t("show-document-text")
              }
              onClick={() => setIsOpened(!isOpened)}
            />
            <SvgButton
              extraClass="bg-active w-100"
              text={t("train-on-this-document")}
              onClick={() => setIsTrainingModalVisible(true)}
            />
            <SvgButton
              extraClass="bg-danger w-100"
              svg={SVGS.trash}
              text={t("delete")}
              confirmations={[`${t("sure")}?`]}
              onClick={handleDelete}
            />
          </div>
        </FloatingDropdown>
      </div>
      {isOpened && (
        <ChunksModal
          hide={() => setIsOpened(false)}
          visible={isOpened}
          chunks={document.chunk_set}
        />
      )}
    </div>
  );
};

const Chunk = ({ content, id }) => {
  const [displayFull, setDisplayFull] = useState(false);

  return (
    <pre
      title={`This chunk is text is from the chunk ${id.toString()}`}
      // onClick={() => setDisplayFull(!displayFull)}
      onDoubleClick={() => setDisplayFull(!displayFull)}
    >
      {displayFull ? content : content.slice(0, 100)}
    </pre>
  );
};

const ChunksModal = ({ visible, hide, chunks }) => {
  const [filteredChunks, setFilteredChunks] = useState(chunks);
  const [search, setSearch] = useState("");
  const { t } = useTranslation();

  useEffect(() => {
    setFilteredChunks(
      chunks.filter((c) =>
        c.content.toLowerCase().includes(search.toLowerCase())
      )
    );
  }, [search]);
  return (
    <Modal minHeight="90vh" visible={visible} hide={hide}>
      <h1 className="fancy-bg padding-big text-center rounded">
        Document content
      </h1>
      <div className={styles.chunkContainer}>
        <div className="d-flex justify-center">
          <input
            type="text"
            className="input w-100"
            placeholder={t("find-something-in-the-document")}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Pill extraClass="bg-active">{chunks.length} chunks</Pill>
        </div>
        {filteredChunks.map((c) => (
          <Chunk key={c.id} content={c.content} id={c.id} />
        ))}
      </div>
    </Modal>
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
