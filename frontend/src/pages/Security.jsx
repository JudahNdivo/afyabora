import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Container, Card, Button, Form, Alert, Spinner } from "react-bootstrap";
import { api } from "../api";
import { SUPPORT_LINK } from "../config";

export default function Security({ embedded = false }) {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "null");

  const [status, setStatus] = useState(null); // { enabled: true or false }
  const [setup, setSetup] = useState(null); // data from the enrol call
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) {
      navigate("/");
      return;
    }
    api("/api/mfa/status")
      .then(setStatus)
      .catch((err) => setError(err.message));
  }, [navigate]);

  if (!user) return null;

  const home = user.role === "admin" ? "/admin" : "/chat";

  async function startSetup() {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      setSetup(await api("/api/mfa/enroll", { method: "POST" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmSetup(e) {
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
        body: { factor_id: setup.factor_id, code },
      });
      // the old password-only token stops working once the authenticator
      // is on, so the new one has to replace it
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));
      setStatus({ enabled: true });
      setSetup(null);
      setCode("");
      setNotice("Authenticator login is on. You will be asked for a code each time you log in.");
    } catch (err) {
      setError(err.message);
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  async function turnOff() {
    if (!window.confirm("Turn off authenticator login for this account?")) return;
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await api("/api/mfa/disable", { method: "POST" });
      setStatus({ enabled: false });
      setNotice("Authenticator login is off.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // the server sends the QR code as raw SVG text, so turn it into an image address
  const qrSrc = setup
    ? "data:image/svg+xml;charset=utf-8," + encodeURIComponent(setup.qr_code)
    : "";

  return (
    <Container
      className={embedded ? "py-2" : "py-4"}
      style={{ maxWidth: 560, ...(embedded ? { marginLeft: 0 } : {}) }}
    >
      {/* inside the admin area the title and navigation are already there */}
      {!embedded && (
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h2 className="mb-0">Security</h2>
          <Button variant="outline-secondary" size="sm" onClick={() => navigate(home)}>
            Back
          </Button>
        </div>
      )}

      {error && <Alert variant="danger">{error}</Alert>}
      {notice && <Alert variant="success">{notice}</Alert>}
      {!status && !error && <Spinner animation="border" />}

      {status && (
        <Card body>
          <h5>Authenticator app login</h5>
          <p className="text-muted">
            Adds a second step when you log in: a 6-digit code from an app such as
            Microsoft Authenticator.
          </p>

          {status.enabled && (
            <>
              <p>
                Status: <strong>on</strong>
              </p>
              <Button variant="outline-danger" onClick={turnOff} disabled={busy}>
                Turn off
              </Button>
              <p className="text-muted small mt-3 mb-0">
                If you lose your phone,{" "}
                <a href={SUPPORT_LINK} target="_blank" rel="noopener noreferrer">
                  contact admin
                </a>{" "}
                from the email address you signed up with and the authenticator can be reset.
              </p>
            </>
          )}

          {!status.enabled && !setup && (
            <>
              <p>
                Status: <strong>off</strong>
              </p>
              <Button variant="primary" onClick={startSetup} disabled={busy}>
                {busy ? "Please wait..." : "Turn on"}
              </Button>
            </>
          )}

          {!status.enabled && setup && (
            <Form onSubmit={confirmSetup}>
              <ol className="ps-3">
                <li className="mb-2">
                  In your authenticator app, add an account and scan this code. If the app
                  already has an older AfyaBora entry, delete it first because each setup
                  creates a new key.
                </li>
              </ol>
              <div className="text-center mb-3">
                <img src={qrSrc} alt="QR code for your authenticator app" width="200" height="200" />
              </div>
              <details className="mb-3">
                <summary>Cannot scan? Enter this key instead</summary>
                <code className="d-block mt-2" style={{ wordBreak: "break-all" }}>
                  {setup.secret}
                </code>
              </details>

              <Form.Group className="mb-3" controlId="setup-code">
                <Form.Label>2. Type the 6-digit code the app shows</Form.Label>
                <Form.Control
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  required
                />
              </Form.Group>

              <Button type="submit" variant="primary" disabled={busy} className="me-2">
                {busy ? "Checking..." : "Confirm"}
              </Button>
              <Button
                type="button"
                variant="link"
                onClick={() => {
                  setSetup(null);
                  setCode("");
                  setError("");
                }}
              >
                Cancel
              </Button>
            </Form>
          )}
        </Card>
      )}
    </Container>
  );
}