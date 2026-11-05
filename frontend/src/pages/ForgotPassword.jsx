import { useState } from "react";
import { Link } from "react-router-dom";
import { Form, Button, Alert } from "react-bootstrap";
import { api } from "../api";
import AuthShell from "../components/AuthShell";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      // the server gives the same answer whether or not the email has an account
      const data = await api("/api/forgot-password", {
        method: "POST",
        body: { email: email.trim() },
        auth: false,
      });
      setNotice(data.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell tagline="We'll send a secure link to reset your password.">
      <Form onSubmit={handleSubmit}>
        <h4 className="mb-3">Reset your password</h4>

        <Form.Group className="mb-3" controlId="email">
          <Form.Label>Email</Form.Label>
          <Form.Control
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </Form.Group>

        {notice && <Alert variant="success" className="py-2">{notice}</Alert>}
        {error && <Alert variant="danger" className="py-2">{error}</Alert>}

        <Button type="submit" variant="primary" className="w-100 py-2 mb-2" disabled={busy}>
          {busy ? "Sending..." : "Send reset link"}
        </Button>
        <p className="text-center mb-0">
          <Link to="/" className="text-dark">Back to log in</Link>
        </p>
      </Form>
    </AuthShell>
  );
}