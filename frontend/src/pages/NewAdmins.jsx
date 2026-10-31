import { useEffect, useState } from "react";
import { Card, Form, Button, Alert, Table } from "react-bootstrap";
import { api } from "../api";

// lists the administrators and lets one promote or remove another
export default function NewAdmins() {
  const [admins, setAdmins] = useState(null);
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    api("/api/admin/admins")
      .then(setAdmins)
      .catch((err) => {
        setAdmins([]);
        setError(err.message);
      });
  }

  useEffect(load, []);

  async function add(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    if (!window.confirm(`Make ${email} an administrator? This is recorded in the log.`)) return;
    setBusy(true);
    try {
      const data = await api("/api/admin/admins", {
        method: "POST",
        body: { email: email.trim() },
      });
      setNotice(data.message);
      setEmail("");
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(a) {
    setError("");
    setNotice("");
    if (!window.confirm(`Remove admin access for ${a.email}?`)) return;
    try {
      const data = await api(`/api/admin/admins/${a.id}`, { method: "DELETE" });
      setNotice(data.message);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div style={{ maxWidth: 820 }}>
      {error && <Alert variant="danger" className="mt-3">{error}</Alert>}
      {notice && <Alert variant="success" className="mt-3">{notice}</Alert>}

      <Card body className="mt-3">
        <h6>Add an administrator</h6>
        <p className="text-muted small">
          The person must already have an account. Type their email address. They will see the
          admin area the next time they log in and should turn on the authenticator straight away.
        </p>
        <Form onSubmit={add} className="d-flex gap-2 flex-wrap">
          <Form.Control
            type="email"
            placeholder="person@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="off"
            style={{ maxWidth: 320 }}
            required
          />
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? "Adding..." : "Make admin"}
          </Button>
        </Form>
      </Card>

      <Card body className="mt-3">
        <h6>Administrators</h6>
        {!admins && <p className="text-muted mb-0">Loading...</p>}
        {admins && admins.length > 0 && (
          <Table size="sm" responsive className="mb-0">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Authenticator</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {admins.map((a) => (
                <tr key={a.id}>
                  <td>{a.username}{a.is_you ? " (you)" : ""}</td>
                  <td>{a.email}</td>
                  <td>{a.authenticator_enabled === null ? "Unknown" : a.authenticator_enabled ? "On" : "Off"}</td>
                  <td className="text-end">
                    {!a.is_you && (
                      <Button variant="link" size="sm" className="text-danger p-0" onClick={() => remove(a)}>
                        Remove
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}