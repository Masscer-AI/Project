import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import {
  deleteDocument,
  generateTrainingCompletions,
  getBigDocument,
  getDocuments,
} from "../../modules/apiCalls";
import styles from "./DocumentsModal.module.css";

import { useTranslation } from "react-i18next";
import { SvgButton } from "../SvgButton/SvgButton";
import { Pill } from "../Pill/Pill";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import { TDocument } from "../../types";
import { Menu } from "../Settings/Settings";
import { Loader } from "../Loader/Loader";
import { Icon } from "../Icon/Icon";

export const DocumentsModal = ({ visible, hide }) => {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState([] as TDocument[]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDocs();
  }, []);

  const getDocs = async () => {
    const docs = await getDocuments();
    setDocuments(docs);
    setLoading(false);
  };

  const removeDoc = (id: number) => {
    setDocuments(documents.filter((d) => d.id !== id));
  };

  const knowledgeOptions = [
    {
      name: t("documents"),
      component: (
        <div className="flex-y gap-big">
          {/* <h3 className="text-center">{t("documents")}</h3> */}
          <p>{t("you-can-use-this-page-to-train-your-model-with-files")}</p>
          <div className="d-flex gap-small">
            <Pill extraClass="">
              {documents.length} {t("documents")}
            </Pill>
            {/* <Pill extraClass="bg-hovered active-on-hover pressable">
            {t("add-documents")}
          </Pill> */}
          </div>
          {loading && <Loader text={t("loading-documents")} />}
          {documents.map((document) => (
            <DocumentCard
              removeDoc={removeDoc}
              key={document.id}
              document={document}
            />
          ))}
        </div>
      ),
      svg: <Icon name="FilePlus" size={20} />,
    },
    {
      name: t("templates"),
      component: (
        <div className="flex-y gap-big">
          <p>{t("document-templates-you-can-replicate-using-ai")}</p>
        </div>
      ),
      svg: <Icon name="FileCode" size={20} />,
    },
  ];

  return (
    <Modal visible={visible} hide={hide} minHeight="90vh">
      <div className="d-flex flex-y gap-big">
        <h2 className="text-center  padding-big rounded ">
          {t("knowledge-base")}
        </h2>
        <Menu options={knowledgeOptions} />
      </div>
    </Modal>
  );
};

const DocumentCard = ({ document, removeDoc }) => {
  const [isOpened, setIsOpened] = useState(false);
  // const [displayBrief, setDisplayBrief] = useState(false);
  const [isTrainingModalVisible, setIsTrainingModalVisible] = useState(false);
  const [hoveredAction, setHoveredAction] = useState<string | null>(null);

  const { t } = useTranslation();

  const handleDelete = async () => {
    const tID = toast.loading(t("deleting-document"));
    try {
      await deleteDocument(document.id);
      toast.success(t("document-deleted"));
      removeDoc(document.id);
    } catch (e) {
      toast.error(t("error-deleting-document"));
      console.log("Error deleting document", e);
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
        <Pill extraClass="bg-hovered">{document.total_tokens} tokens</Pill>
      </div>

      <p>{document.brief}</p>
      <div className="d-flex justify-center gap-small">
        <FloatingDropdown
          bottom="100%"
          opener={<SvgButton text={t("options")} svg={<Icon name="Menu" size={20} />} />}
        >
          <div className="w-[200px] flex flex-col gap-3 p-4 bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl shadow-lg">
            <button
              className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
                hoveredAction === 'show-hide' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredAction('show-hide')}
              onMouseLeave={() => setHoveredAction(null)}
              onClick={() => setIsOpened(!isOpened)}
            >
              <span>{isOpened ? t("hide-document-text") : t("show-document-text")}</span>
            </button>
            <button
              className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
                hoveredAction === 'train' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredAction('train')}
              onMouseLeave={() => setHoveredAction(null)}
              onClick={() => setIsTrainingModalVisible(true)}
            >
              <span>{t("train-on-this-document")}</span>
            </button>
            <button
              className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
                hoveredAction === 'delete' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(220,38,38,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(220,38,38,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredAction('delete')}
              onMouseLeave={() => setHoveredAction(null)}
              onClick={() => {
                if (window.confirm(`${t("sure")}?`)) {
                  handleDelete();
                }
              }}
            >
              <Icon name="Trash2" size={20} />
              <span>{t("delete")}</span>
            </button>
          </div>
        </FloatingDropdown>
      </div>
      {isOpened && (
        <ChunksModal
          hide={() => setIsOpened(false)}
          visible={isOpened}
          // chunks={document.chunk_set}
          documentId={document.id}
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

const ChunksModal = ({ visible, hide, documentId }) => {
  const [chunks, setChunks] = useState([] as any[]);
  const [filteredChunks, setFilteredChunks] = useState([] as any[]);
  const [search, setSearch] = useState("");
  const { t } = useTranslation();

  useEffect(() => {
    getChunks();
  }, []);

  const getChunks = async () => {
    const doc = await getBigDocument(documentId);
    setChunks(doc.chunk_set);
    setFilteredChunks(doc.chunk_set);
  };

  useEffect(() => {
    setFilteredChunks(
      chunks.filter((c) =>
        c.content.toLowerCase().includes(search.toLowerCase())
      )
    );
  }, [search]);
  return (
    <Modal minHeight="90vh" visible={visible} hide={hide}>
      <h2 className=" padding-medium text-center rounded">
        {t("document-chunks")}
      </h2>
      <div className={styles.chunkContainer}>
        <div className="d-flex justify-center gap-big">
          <input
            type="text"
            className="input w-100"
            placeholder={t("find-something-in-the-document")}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Pill extraClass="bg-active w-50">Total: {chunks.length}</Pill>
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
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
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
        <button
          className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
            hoveredButton === 'generate' 
              ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
              : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
          }`}
          style={{ transform: 'none' }}
          onMouseEnter={() => setHoveredButton('generate')}
          onMouseLeave={() => setHoveredButton(null)}
          onClick={generateTrainingData}
        >
          <Icon name="Dumbbell" size={20} />
          <span>Generate</span>
        </button>
      </div>
    </Modal>
  );
};
