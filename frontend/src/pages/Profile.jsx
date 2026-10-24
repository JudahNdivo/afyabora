import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Container, Card, Button, Form, Alert, Spinner } from "react-bootstrap";
import { api } from "../api";

// readable names for the ways an account can sign in
const METHOD_NAMES = { email: "Email and password", google: "Google" };

export default function Profile() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "null");

  const [profile, setProfile] = useState(null);
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [showDelete, setShowDelete] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState("");

  useEffect(() => {
    if (!user) {
      navigate("/");
      return;
    }
    api("/api/profile")
      .then((data) => {
        setProfile(data);
        setUsername(data.username || "");
      })
      .catch((err) => setError(err.message));
  }, [navigate]);

  if (!user) return null;

  const home = user.role === "admin" ? "/admin" : "/chat";

  async function saveUsername(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const data = await api("/api/profile", {
        method: "PUT",
        body: { username },
      });
      setProfile({ ...profile, username: data.username });
      // keep the saved copy in step so the rest of the app shows the new name
      localStorage.setItem("user", JSON.stringify({ ...user, username: data.username }));
      setNotice("Username updated.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteAccount(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/api/profile", { method: "DELETE", body: { confirm_email: confirmEmail } });
      localStorage.clear();
      navigate("/");
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const methods = profile
    ? profile.sign_in_methods.map((m) => METHOD_NAMES[m] || m).join(", ")
    : "";

  return (
    <Container className="py-4" style={{ maxWidth: 560 }}>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="mb-0">Your profile</h2>
        <Button variant="outline-secondary" size="sm" onClick={() => navigate(home)}>
          Back
        </Button>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}
      {notice && <Alert variant="success">{notice}</Alert>}
      {!profile && !error && <Spinner animation="border" />}

      {profile && (
        <>
          <Card body className="mb-3">
            <Form onSubmit={saveUsername}>
              <Form.Group className="mb-3" controlId="profile-username">
                <Form.Label>Username</Form.Label>
                <Form.Control
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  minLength={2}
                  maxLength={40}
                  required
                />
              </Form.Group>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={busy || username.trim() === (profile.username || "")}
              >
                Save username
              </Button>
            </Form>

            <hr />

            <div className="mb-2">
              <div className="text-muted small">Email</div>
              <div>{profile.email}</div>
            </div>
            <div className="mb-2">
              <div className="text-muted small">Signs in with</div>
              <div>{methods}</div>
            </div>
            <div>
              <div className="text-muted small">Authenticator app login</div>
              <div className="d-flex align-items-center gap-2">
                <span>{profile.authenticator_enabled ? "On" : "Off"}</span>
                <Button variant="link" size="sm" className="p-0" onClick={() => navigate("/security")}>
                  Manage
                </Button>
              </div>
            </div>
          </Card>

          {profile.role !== "admin" && (
            <Card body border="danger">
              <h6>Delete account</h6>
              <p className="text-muted small">
                This permanently deletes your account and all your conversations. It cannot be undone.
              </p>
              {!showDelete && (
                <Button variant="outline-danger" size="sm" onClick={() => setShowDelete(true)}>
                  Delete my account
                </Button>
              )}
              {showDelete && (
                <Form onSubmit={deleteAccount}>
                  <Form.Group className="mb-3" controlId="delete-email">
                    <Form.Label>Type your email address to confirm</Form.Label>
                    <Form.Control
                      type="email"
                      value={confirmEmail}
                      onChange={(e) => setConfirmEmail(e.target.value)}
                      placeholder={profile.email}
                      autoComplete="off"
                      required
                    />
                  </Form.Group>
                  <Button type="submit" variant="danger" size="sm" disabled={busy} className="me-2">
                    {busy ? "Deleting..." : "Delete permanently"}
                  </Button>
                  <Button
                    type="button"
                    variant="link"
                    size="sm"
                    onClick={() => {
                      setShowDelete(false);
                      setConfirmEmail("");
                    }}
                  >
                    Cancel
                  </Button>
                </Form>
              )}
            </Card>
          )}
        </>
      )}
    </Container>
  );
}