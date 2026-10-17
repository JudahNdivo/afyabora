import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

function validatePassword(password) {
  const errors = [];
  if (password.length < 8) errors.push("at least 8 characters");
  if (!/[A-Z]/.test(password)) errors.push("one uppercase letter");
  if (!/[a-z]/.test(password)) errors.push("one lowercase letter");
  if (!/[0-9]/.test(password)) errors.push("one number");
  return errors;
}

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";

  function switchMode(next) {
    setMode(next);
    setError("");
  }

  async function doLogin() {
    const data = await api("/api/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    // a login that needs a 2FA code will be handled here later
    if (!data.access_token) throw new Error("Login could not be completed");
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("user", JSON.stringify(data.user));
    navigate("/chat");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (isSignup) {
      const problems = validatePassword(password);
      if (problems.length > 0) {
        setError(`Password needs: ${problems.join(", ")}`);
        return;
      }
    }

    setBusy(true);
    try {
      if (isSignup) {
        await api("/api/signup", {
          method: "POST",
          body: { email, password, username },
          auth: false,
        });
      }
      await doLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-side">
        <div className="auth-side-content">
          <div className="brand-mark">A</div>
          <h1>AfyaBora</h1>
          <p>Honest, judgment-free answers about sexual health, in English or Kiswahili.</p>
        </div>
      </div>

      <div className="auth-main">
        <div className="auth-card">
          <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${!isSignup ? "active" : ""}`}
              onClick={() => switchMode("login")}
            >
              Log in
            </button>
            <button
              type="button"
              className={`auth-tab ${isSignup ? "active" : ""}`}
              onClick={() => switchMode("signup")}
            >
              Sign up
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            {isSignup && (
              <label className="field">
                <span>Username</span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  required
                />
              </label>
            )}

            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </label>

            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
              />
            </label>

            {!isSignup && (
              <p className="forgot-link">
                {/* points at the Flask page until the reset flow is ported */}
                <a href="http://127.0.0.1:5000/forgot-password">Forgot password?</a>
              </p>
            )}

            {error && <p className="form-error">{error}</p>}

            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? "Please wait..." : isSignup ? "Sign up" : "Log in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}