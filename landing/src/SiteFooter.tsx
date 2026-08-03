import { Link } from "react-router-dom";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <p className="site-footer__brand">Masscer</p>
        <nav className="site-footer__nav" aria-label="Legal">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Service</Link>
          <a href="mailto:masscer.ai@gmail.com">Contact</a>
        </nav>
      </div>
    </footer>
  );
}
