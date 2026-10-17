import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Container, Row, Col, Card, Alert, Spinner, ProgressBar, Button } from "react-bootstrap";
import { api } from "../api";

const ACRONYMS = ["hiv", "hpv", "sti"];

// readable labels for language codes and topic names
function pretty(label) {
  if (label === "sw") return "Kiswahili";
  if (label === "en") return "English";
  return ACRONYMS.includes(label)
    ? label.toUpperCase()
    : label.charAt(0).toUpperCase() + label.slice(1);
}

// shows a count as a share of the biggest count in the list
function BarList({ rows }) {
  if (!rows.length) return <p className="text-muted mb-0">No data yet.</p>;
  const max = Math.max(...rows.map((r) => r.count));
  return rows.map((r) => (
    <div key={r.label} className="mb-2">
      <div className="d-flex justify-content-between small">
        <span>{pretty(r.label)}</span>
        <span>{r.count}</span>
      </div>
      <ProgressBar now={(r.count / max) * 100} />
    </div>
  ));
}

// turns the list of days that had questions into the last 14 days,
// filling the quiet days with zero
function lastDays(perDay, n = 14) {
  const counts = Object.fromEntries(perDay.map((d) => [d.day, d.count]));
  const out = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    // en-CA gives the YYYY-MM-DD format the server uses
    const key = d.toLocaleDateString("en-CA", { timeZone: "Africa/Nairobi" });
    out.push({ day: key, count: counts[key] || 0 });
  }
  return out;
}

function seconds(ms) {
  return ms == null ? "n/a" : `${(ms / 1000).toFixed(1)} s`;
}

// quotes a value if it contains a comma, quote or line break
function csvCell(value) {
  const s = String(value ?? "");
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// one long table (section, label, value) that opens cleanly in Excel or Sheets
function buildCsv(stats) {
  const sec = (ms) => (ms == null ? "" : (ms / 1000).toFixed(1));
  const stamp = new Date().toLocaleString("en-GB", { timeZone: "Africa/Nairobi" });
  const rows = [
    ["section", "label", "value"],
    ["meta", "Exported at (Nairobi time)", stamp],
    ["summary", "Registered users", stats.total_users],
    ["summary", "Questions answered", stats.total_queries],
    ["summary", "Median response time (seconds)", sec(stats.median_response_ms)],
    ["summary", "Average response time (seconds)", sec(stats.avg_response_ms)],
    ...stats.by_language.map((r) => ["language", pretty(r.label), r.count]),
    ...stats.by_disease.map((r) => ["topic", pretty(r.label), r.count]),
    ...stats.per_day.map((d) => ["day", d.day, d.count]),
  ];
  return rows.map((r) => r.map(csvCell).join(",")).join("\r\n");
}

function downloadCsv(stats) {
  const blob = new Blob([buildCsv(stats)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const day = new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Nairobi" });
  const link = document.createElement("a");
  link.href = url;
  link.download = `afyabora-usage-${day}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Admin() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "null");
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  // the server is what actually refuses non-admins; this only decides
  // whether to bother asking
  useEffect(() => {
    if (!user) {
      navigate("/");
      return;
    }
    if (user.role !== "admin") return;
    api("/api/admin/stats")
      .then(setStats)
      .catch((err) => setError(err.message));
  }, [navigate]);

  if (!user) return null;

  if (user.role !== "admin") {
    return (
      <Container className="py-5" style={{ maxWidth: 520 }}>
        <Alert variant="warning">This page is for administrators only.</Alert>
        <a href="/chat">Back to chat</a>
      </Container>
    );
  }

  function logout() {
    localStorage.clear();
    navigate("/");
  }

  const days = stats ? lastDays(stats.per_day) : [];
  const maxDay = Math.max(1, ...days.map((d) => d.count));

  return (
    <Container className="py-4">
      <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        <h2 className="mb-0">Usage dashboard</h2>
        <div className="d-flex gap-2 align-items-center no-print">
          <Button variant="primary" size="sm" disabled={!stats} onClick={() => downloadCsv(stats)}>
            Download CSV
          </Button>
          <Button variant="outline-secondary" size="sm" disabled={!stats} onClick={() => window.print()}>
            Print / save as PDF
          </Button>
          <Button variant="outline-secondary" size="sm" onClick={logout}>
            Log out
          </Button>
        </div>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}
      {!stats && !error && <Spinner animation="border" />}

      {stats && (
        <>
          <Row className="g-3 mb-3">
            <Col md={3} sm={6}>
              <Card body>
                <div className="text-muted small">Registered users</div>
                <div className="fs-2">{stats.total_users}</div>
              </Card>
            </Col>
            <Col md={3} sm={6}>
              <Card body>
                <div className="text-muted small">Questions answered</div>
                <div className="fs-2">{stats.total_queries}</div>
              </Card>
            </Col>
            <Col md={3} sm={6}>
              <Card body>
                <div className="text-muted small">Median response time</div>
                <div className="fs-2">{seconds(stats.median_response_ms)}</div>
              </Card>
            </Col>
            <Col md={3} sm={6}>
              <Card body>
                <div className="text-muted small">Average response time</div>
                <div className="fs-2">{seconds(stats.avg_response_ms)}</div>
              </Card>
            </Col>
          </Row>

          <Row className="g-3 mb-3">
            <Col md={6}>
              <Card body>
                <h6 className="mb-3">Questions by language</h6>
                <BarList rows={stats.by_language} />
              </Card>
            </Col>
            <Col md={6}>
              <Card body>
                <h6 className="mb-3">Questions by topic</h6>
                <BarList rows={stats.by_disease} />
              </Card>
            </Col>
          </Row>

          <Card body>
            <h6 className="mb-3">Questions per day, last 14 days</h6>
            <div className="d-flex align-items-end gap-1" style={{ height: 140 }}>
              {days.map((d) => (
                <div
                  key={d.day}
                  className="flex-fill text-center"
                  title={`${d.day}: ${d.count}`}
                >
                  <div
                    style={{
                      height: `${(d.count / maxDay) * 100}px`,
                      minHeight: d.count ? 4 : 1,
                      background: "var(--primary)",
                      borderRadius: 3,
                    }}
                  />
                </div>
              ))}
            </div>
            <div className="d-flex justify-content-between small text-muted mt-1">
              <span>{days[0]?.day}</span>
              <span>{days[days.length - 1]?.day}</span>
            </div>
          </Card>
        </>
      )}
    </Container>
  );
}