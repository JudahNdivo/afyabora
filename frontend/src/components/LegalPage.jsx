import { Link } from "react-router-dom";
import "../styles/legal.css";

// the frame shared by the privacy policy and the terms of use
export default function LegalPage({ title, updated, children }) {
  return (
    <div className="legal-page">
      <div className="legal-card">
        <Link to="/" className="legal-back">Back to AfyaBora</Link>
        <h1>{title}</h1>
        <p className="legal-updated">Last updated {updated}</p>
        {children}
        <p className="legal-links">
          <Link to="/privacy">Privacy policy</Link> · <Link to="/terms">Terms of use</Link>
        </p>
      </div>
    </div>
  );
}