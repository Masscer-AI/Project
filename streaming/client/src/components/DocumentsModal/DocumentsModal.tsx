import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import { getDocuments } from "../../modules/apiCalls";
import styles from "./DocumentsModal.module.css";
import { Card } from "../Card/Card";
type TDocument = {
  id: number;
};

export const DocumentsModal = ({ visible, hide }) => {
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
    <Modal visible={visible} hide={hide}>
      <h3 className="text-center">Files</h3>
      <p className="text-center">
        You can use this page to train your model with documents.
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
  const [displayChunks, setdisplayChunks] = useState(false);

  return (
    <div className={styles.documentCard}>
      <h3>{document.name}</h3>
      <p>{document.chunk_count}</p>
      <p>{document.brief}</p>
      <button className="button" onClick={() => setIsOpened(!isOpened)}>
        {isOpened ? "Close" : "Show"} document text
      </button>
      {isOpened && <textarea readOnly value={document.text}></textarea>}
      <button
        className="button"
        onClick={() => setdisplayChunks(!displayChunks)}
      >
        {displayChunks ? "Close" : "Show"} chunks
      </button>
      <div className="d-flex wrap-wrap gap-small">
        {displayChunks &&
          document.chunk_set.map((c) => <ChunkCard key={c.id} chunk={c} />)}
      </div>
    </div>
  );
};

const ChunkCard = ({ chunk }) => {
  return <Card>{chunk.content.slice(0, 100)}</Card>;
};
