// the split screen used by the login page, reused for the password pages
export default function AuthShell({ tagline, children }) {
  return (
    <div className="auth-screen">
      <div className="auth-side">
        <div className="auth-side-content">
          <div className="brand-mark">A</div>
          <h1>AfyaBora</h1>
          <p>{tagline}</p>
        </div>
      </div>

      <div className="auth-main">
        <div className="auth-mobile-brand">
          <div className="brand-mark">A</div>
          <span>AfyaBora</span>
        </div>
        <div className="auth-card">{children}</div>
      </div>
    </div>
  );
}