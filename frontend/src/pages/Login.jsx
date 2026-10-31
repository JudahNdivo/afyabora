import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { api } from "../api";
import { Form, Button, Alert } from "react-bootstrap";
import { SUPPORT_LINK } from "../config";
import GoogleLogo from "../components/GoogleLogo";

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
  const location = useLocation();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(location.state?.error || "");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  // set when the first step was right but an authenticator code is still
  // needed; it can also arrive from the Google callback page
  const [mfa, setMfa] = useState(location.state?.mfa || null);
  const [code, setCode] = useState("");

  const isSignup = mode === "signup";

  function switchMode(next) {
    setMode(next);
    setError("");
    setNotice("");
    // clear the fields so nothing typed or filled in carries to the other tab
    setEmail("");
    setPassword("");
  }

  function finishLogin(data) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("user", JSON.stringify(data.user));
    // administrators go to the dashboard, everyone else to the chat
    navigate(data.user.role === "admin" ? "/admin" : "/chat");
  }

  async function doLogin() {
    const data = await api("/api/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    });

    if (data.mfa_required) {
      // the password-only token is kept in memory, never in storage
      setMfa({ token: data.mfa_token, factorId: data.factor_id });
      setPassword("");
      return;
    }
    if (!data.access_token) throw new Error("Login could not be completed");
    finishLogin(data);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setNotice("");

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
        const res = await api("/api/signup", {
          method: "POST",
          body: { email, password, username },
          auth: false,
        });
        if (res.needs_confirmation) {
          // the account is not usable until the email link is clicked
          setMode("login");
          setUsername("");
          setPassword("");
          setNotice("Check your inbox for a confirmation link. Clicking it signs you in.");
          return;
        }
      }
      await doLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleCode(e) {
    e.preventDefault();
    setError("");

    if (!/^\d{6}$/.test(code)) {
      setError("Enter the 6-digit code from your authenticator app");
      return;
    }

    setBusy(true);
    try {
      const data = await api("/api/mfa/verify", {
        method: "POST",
        body: { factor_id: mfa.factorId, code },
        token: mfa.token,
        auth: false,
      });
      finishLogin(data);
    } catch (err) {
      setError(err.message);
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  function cancelCode() {
    setMfa(null);
    setCode("");
    setError("");
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
        <div className="auth-mobile-brand">
          <div className="brand-mark">A</div>
          <span>AfyaBora</span>
        </div>
        <div className="auth-card">
          {mfa ? (
            <Form onSubmit={handleCode}>
              <h4 className="mb-2">Enter your code</h4>
              <p className="text-muted">
                Open your authenticator app and type the 6-digit code for AfyaBora.
              </p>

              <Form.Group className="mb-3" controlId="code">
                <Form.Label>Authenticator code</Form.Label>
                <Form.Control
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  autoFocus
                  required
                />
              </Form.Group>

              {error && <Alert variant="danger" className="py-2">{error}</Alert>}

              <Button type="submit" variant="primary" className="w-100 py-2 mb-2" disabled={busy}>
                {busy ? "Checking..." : "Verify"}
              </Button>
              <Button type="button" variant="link" className="w-100" onClick={cancelCode}>
                Back to log in
              </Button>
              <p className="text-muted small text-center mt-2 mb-0">
                Lost your phone?{" "}
                <a href={SUPPORT_LINK} target="_blank" rel="noopener noreferrer">
                  Contact admin
                </a>{" "}
                from the email address you signed up with.
              </p>
            </Form>
          ) : (
            <>
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

              <Form onSubmit={handleSubmit}>
                {isSignup && (
                  <Form.Group className="mb-3" controlId="username">
                    <Form.Label>Username</Form.Label>
                    <Form.Control
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      autoComplete="username"
                      required
                    />
                  </Form.Group>
                )}

                <Form.Group className="mb-3" controlId="email">
                  <Form.Label>Email</Form.Label>
                  <Form.Control
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="off"
                    required
                  />
                </Form.Group>

                <Form.Group className="mb-2" controlId="password">
                  <Form.Label>Password</Form.Label>
                  <Form.Control
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                    required
                  />
                </Form.Group>

                {!isSignup && (
                  <p className="forgot-link">
                    {/* points at the Flask page until the reset flow is ported */}
                    <a href="http://127.0.0.1:5000/forgot-password">Forgot password?</a>
                  </p>
                )}

                {notice && <Alert variant="success" className="py-2">{notice}</Alert>}
                {error && <Alert variant="danger" className="py-2">{error}</Alert>}

                <Button type="submit" variant="primary" className="w-100 py-2" disabled={busy}>
                  {busy ? "Please wait..." : isSignup ? "Sign up" : "Log in"}
                </Button>
              </Form>

              <div className="auth-divider"><span>or</span></div>

              {/* a plain link: the whole page moves to Google and back */}
              <a className="btn-google" href="/api/auth/google">
                <GoogleLogo />
                Continue with Google
              </a>
            </>
          )}
        </div>
      </div>
    </div>
  );
}