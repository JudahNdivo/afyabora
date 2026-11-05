import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Form, Button, Alert } from "react-bootstrap";
import { api } from "../api";
import AuthShell from "../components/AuthShell";

// same rules as the sign-up form
function validatePassword(password) {
  const errors = [];
  if (password.length < 8) errors.push("at least 8 characters");
  if (!/[A-Z]/.test(password)) errors.push("one uppercase letter");
  if (!/[a-z]/.test(password)) errors.push("one lowercase letter");
  if (!/[0-9]/.test(password)) errors.push("one number");
  return errors;
}

export default function ResetPassword() {
  const navigate = useNavigate();
  const [token, setToken] = useState(null);
  const [checked, setChecked] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  // the email link brings the token after a "#" in the address
  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    setToken(params.get("access_token"));
    setChecked(true);
    // take the token out of the address bar
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    const problems = validatePassword(password);
    if (problems.length > 0) {
      setError(`Password needs: ${problems.join(", ")}`);
      return;
    }
    if (password !== confirm) {
      setError("The two passwords do not match");
      return;
    }

    setBusy(true);
    try {
      await api("/api/reset-password", {
        method: "POST",
        body: { access_token: token, new_password: password },
        auth: false,
      });
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!checked) return null;

  return (
    <AuthShell tagline="Choose a new password to get back into your account.">
      {done ? (
        <>
          <h4 className="mb-2">Password updated</h4>
          <p className="text-muted">You can now log in with your new password.</p>
          <Button variant="primary" className="w-100 py-2" onClick={() => navigate("/")}>
            Log in
          </Button>
        </>
      ) : !token ? (
        <>
          <h4 className="mb-2">This link has expired</h4>
          <p className="text-muted">
            The reset link is not valid any more. Links work once and only for a short time.
          </p>
          <Link to="/forgot-password" className="btn btn-primary w-100 py-2">
            Send a new link
          </Link>
        </>
      ) : (
        <Form onSubmit={handleSubmit}>
          <h4 className="mb-3">Choose a new password</h4>

          <Form.Group className="mb-3" controlId="password">
            <Form.Label>New password</Form.Label>
            <Form.Control
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </Form.Group>

          <Form.Group className="mb-3" controlId="confirm">
            <Form.Label>Confirm new password</Form.Label>
            <Form.Control
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              required
            />
          </Form.Group>

          {error && <Alert variant="danger" className="py-2">{error}</Alert>}

          <Button type="submit" variant="primary" className="w-100 py-2" disabled={busy}>
            {busy ? "Saving..." : "Update password"}
          </Button>
        </Form>
      )}
    </AuthShell>
  );
}