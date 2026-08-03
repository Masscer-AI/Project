import { Link } from "react-router-dom";
import { Markdown } from "./markdown";
import { SiteFooter } from "./SiteFooter";
import privacyMd from "./content/privacy.md?raw";
import termsMd from "./content/terms.md?raw";

type DocId = "privacy" | "terms";

const DOCS: Record<DocId, { title: string; source: string }> = {
  privacy: { title: "Privacy Policy", source: privacyMd },
  terms: { title: "Terms of Service", source: termsMd },
};

export function LegalPage({ docId }: { docId: DocId }) {
  const doc = DOCS[docId];
  return (
    <div className="page page--legal">
      <div className="atmosphere atmosphere--subtle" aria-hidden="true" />

      <header className="topbar">
        <Link className="logo" to="/">
          Masscer
        </Link>
        <nav className="topbar__nav">
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
          <a className="btn btn--primary" href="https://app.masscer.ai/signup">
            Get started
          </a>
        </nav>
      </header>

      <main className="legal">
        <p className="legal__back">
          <Link to="/">← Back to home</Link>
        </p>
        <h1>{doc.title}</h1>
        <Markdown source={doc.source} />
      </main>

      <SiteFooter />
    </div>
  );
}
