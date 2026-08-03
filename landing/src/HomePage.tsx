import { Link } from "react-router-dom";
import { SiteFooter } from "./SiteFooter";

const APP_URL = "https://app.masscer.ai";

const FEATURES = [
  {
    title: "Create AI agents",
    description:
      "Build professional-grade AI agents with your data. Use them to answer messages, create videos and documents, and automate work.",
  },
  {
    title: "Automate WhatsApp",
    description:
      "Let your agent handle customer inquiries, support tickets, and conversations 24/7 on WhatsApp.",
  },
  {
    title: "Embed on your website",
    description:
      "Add a chat widget with your AI agent in minutes. Copy, paste, and start attending visitors live.",
  },
  {
    title: "Manage relationships",
    description:
      "Stay on top of client and team conversations with AI insights—scale communication without losing the human touch.",
  },
];

export function HomePage() {
  return (
    <div className="page">
      <div className="atmosphere" aria-hidden="true" />

      <header className="topbar">
        <a className="logo" href="/">
          Masscer
        </a>
        <nav className="topbar__nav">
          <Link to="/privacy">Privacy</Link>
          <a className="btn btn--ghost" href={`${APP_URL}/login`}>
            Log in
          </a>
          <a className="btn btn--primary" href={`${APP_URL}/signup`}>
            Get started
          </a>
        </nav>
      </header>

      <main>
        <section className="hero">
          <p className="hero__brand">Masscer</p>
          <h1 className="hero__headline">AI agents for real business work</h1>
          <p className="hero__lede">
            Masscer AI lets you create professional-grade AI agents, automate WhatsApp,
            embed chat on your website, and manage client relationships—customized to your
            unique needs.
          </p>
          <div className="hero__cta">
            <a className="btn btn--primary btn--lg" href={`${APP_URL}/signup`}>
              Get started
            </a>
            <a className="btn btn--ghost btn--lg" href={`${APP_URL}/login`}>
              Open the app
            </a>
          </div>
          <p className="hero__note">No credit card required</p>
        </section>

        <section className="features" aria-labelledby="features-title">
          <h2 id="features-title" className="features__title">
            What you can do
          </h2>
          <ul className="features__grid">
            {FEATURES.map((f) => (
              <li key={f.title} className="feature">
                <h3>{f.title}</h3>
                <p>{f.description}</p>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
