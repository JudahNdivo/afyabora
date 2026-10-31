import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Form, Alert, Spinner } from "react-bootstrap";
import { api } from "../api";
import "../styles/profile.css";

// readable names for the ways an account can sign in
const METHOD_NAMES = { email: "Email and password", google: "Google" };

export default function Profile({ embedded = false }) {
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
  const shownName = (profile && profile.username) || user.username || "";

  return (
    <div className={`profile-page ${embedded ? "embedded" : ""}`}>
      {!embedded && (
        <div className="profile-top">
          <h2>Your profile</h2>
          <Button variant="outline-secondary" size="sm" onClick={() => navigate(home)}>
            Back
          </Button>
        </div>
      )}

      {error && <Alert variant="danger">{error}</Alert>}
      {notice && <Alert variant="success">{notice}</Alert>}
      {!profile && !error && <Spinner animation="border" />}

      {profile && (
        <>
          <div className="profile-hero">
            <div className="profile-avatar">{shownName.charAt(0).toUpperCase() || "?"}</div>
            <div className="profile-hero-text">
              <p className="profile-name">{shownName}</p>
              <div className="profile-email">{profile.email}</div>
              <span className="profile-role">
                {profile.role === "admin" ? "Administrator" : "Member"}
              </span>
            </div>
          </div>

          <div className="profile-card">
            <h3>Username</h3>
            <Form onSubmit={saveUsername} className="d-flex gap-2 flex-wrap">
              <Form.Control
                aria-label="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                minLength={2}
                maxLength={40}
                required
                style={{ flex: "1 1 200px" }}
              />
              <Button
                type="submit"
                variant="primary"
                disabled={busy || username.trim() === (profile.username || "")}
              >
                Save
              </Button>
            </Form>
          </div>

          <div className="profile-card">
            <h3>Account</h3>
            <div className="profile-row">
              <span className="profile-label">Email</span>
              <span className="profile-value">{profile.email}</span>
            </div>
            <div className="profile-row">
              <span className="profile-label">Signs in with</span>
              <span className="profile-value">{methods}</span>
            </div>
            <div className="profile-row">
              <span className="profile-label">Authenticator app login</span>
              <span className="profile-value d-flex align-items-center gap-2">
                <span className={`status-pill ${profile.authenticator_enabled ? "on" : ""}`}>
                  {profile.authenticator_enabled ? "On" : "Off"}
                </span>
                <Button
                  variant="link"
                  size="sm"
                  className="p-0"
                  onClick={() => navigate(embedded ? "/admin/security" : "/security")}
                >
                  Manage
                </Button>
              </span>
            </div>
          </div>

          {profile.role !== "admin" && (
            <div className="profile-card profile-danger">
              <h3>Delete account</h3>
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
            </div>
          )}
        </>
      )}
    </div>
  );
}