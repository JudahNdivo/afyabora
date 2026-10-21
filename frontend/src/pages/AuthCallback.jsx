import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Container, Alert, Spinner } from "react-bootstrap";
import { api } from "../api";

export default function AuthCallback() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const started = useRef(false);

  useEffect(() => {
    // run once, even if React renders this page twice
    if (started.current) return;
    started.current = true;

    // Supabase sends the session back in the address, after the #
    const hash = new URLSearchParams(window.location.hash.slice(1));
    const query = new URLSearchParams(window.location.search);
    const problem =
      hash.get("error_description") || query.get("error_description") ||
      hash.get("error") || query.get("error");
    const token = hash.get("access_token");

    // take the token out of the address bar and the browser history
    window.history.replaceState(null, "", window.location.pathname);

    if (problem) {
      setError(problem);
      return;
    }
    if (!token) {
      setError("Google sign-in did not return a session. Please try again.");
      return;
    }

    api("/api/google-login", { method: "POST", token, auth: false })
      .then((data) => {
        if (data.mfa_required) {
          // hand the password-level token to the code screen, in memory only
          navigate("/", {
            replace: true,
            state: { mfa: { token: data.mfa_token, factorId: data.factor_id } },
          });
          return;
        }
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("user", JSON.stringify(data.user));
        navigate(data.user.role === "admin" ? "/admin" : "/chat", { replace: true });
      })
      .catch((err) => setError(err.message));
  }, [navigate]);

  return (
    <Container className="py-5 text-center" style={{ maxWidth: 480 }}>
      {error ? (
        <>
          <Alert variant="danger">{error}</Alert>
          <a href="/">Back to log in</a>
        </>
      ) : (
        <>
          <Spinner animation="border" />
          <p className="mt-3 text-muted">Finishing sign-in...</p>
        </>
      )}
    </Container>
  );
}