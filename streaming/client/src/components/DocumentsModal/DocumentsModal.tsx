import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import { getDocuments } from "../../modules/apiCalls";
import styles from "./DocumentsModal.module.css";
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
      <h3 className="text-center">Documents</h3>
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
      <button className="button" onClick={() => setIsOpened(!isOpened)}>
        {isOpened ? "Close" : "Show"} document text
      </button>
      {isOpened && <textarea readOnly>{document.text}</textarea>}
      <button
        className="button"
        onClick={() => setdisplayChunks(!displayChunks)}
      >
        {displayChunks ? "Close" : "Show"} chunks
      </button>
      {displayChunks &&
        document.chunk_set.map((c) => <span key={c.id}>{c.id} </span>)}
    </div>
  );
};
