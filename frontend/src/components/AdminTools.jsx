import { useEffect, useState } from "react";
import { Card, Form, Button, Alert, Table } from "react-bootstrap";
import { api } from "../api";

const ACTION_NAMES = {
  reset_authenticator: "Authenticator reset",
  reset_authenticator_failed: "Reset failed",
  make_admin: "Made admin",
  remove_admin: "Removed admin",
};

function when(iso) {
  return new Date(iso).toLocaleString("en-GB", { timeZone: "Africa/Nairobi" });
}

// lets an administrator reset one person's authenticator by typing their
// email, and shows the log of every reset; there is no list of users
export default function AdminTools() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [actions, setActions] = useState(null);

  function loadActions() {
    api("/api/admin/actions")
      .then(setActions)
      .catch(() => setActions([]));
  }

  useEffect(loadActions, []);

  async function reset(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    if (!window.confirm(`Reset the authenticator for ${email}? This is recorded in the log.`)) return;
    setBusy(true);
    try {
      const data = await api("/api/admin/reset-authenticator", {
        method: "POST",
        body: { email: email.trim() },
      });
      setNotice(data.message);
      setEmail("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      loadActions();
    }
  }

  return (
    <>
      <Card body className="mt-3 no-print">
        <h6>Reset a user's authenticator</h6>
        <p className="text-muted small">
          For anyone who lost their phone, including another administrator (never yourself). Type their email address. They can then log in with
          their password and set the authenticator up again. Every reset is recorded below.
        </p>
        {error && <Alert variant="danger">{error}</Alert>}
        {notice && <Alert variant="success">{notice}</Alert>}
        <Form onSubmit={reset} className="d-flex gap-2 flex-wrap">
          <Form.Control
            type="email"
            placeholder="user@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="off"
            style={{ maxWidth: 320 }}
            required
          />
          <Button type="submit" variant="outline-danger" disabled={busy}>
            {busy ? "Resetting..." : "Reset authenticator"}
          </Button>
        </Form>
      </Card>

      <Card body className="mt-3 no-print">
        <h6>Recent admin actions</h6>
        {!actions && <p className="text-muted mb-0">Loading...</p>}
        {actions && actions.length === 0 && <p className="text-muted mb-0">Nothing recorded yet.</p>}
        {actions && actions.length > 0 && (
          <Table size="sm" responsive className="mb-0">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Account</th>
                <th>By</th>
              </tr>
            </thead>
            <tbody>
              {actions.map((a, i) => (
                <tr key={i}>
                  <td>{when(a.created_at)}</td>
                  <td>{ACTION_NAMES[a.action] || a.action}</td>
                  <td>{a.target_email}</td>
                  <td>{a.admin_email}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}