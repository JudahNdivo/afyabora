import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Container, Alert } from "react-bootstrap";
import "../styles/chat.css";
import "../styles/admin.css";

const TITLES = {
  "/admin": "Dashboard",
  "/admin/reset": "Reset authenticator",
  "/admin/admins": "Administrators",
  "/admin/security": "Security",
  "/admin/profile": "Profile",
};

// the frame around every admin page: a sidebar and a title bar. The server is
// what really refuses non-admins; this only decides what to show.
export default function AdminLayout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const user = JSON.parse(localStorage.getItem("user") || "null");
  const [open, setOpen] = useState(false);

  if (!user) {
    navigate("/");
    return null;
  }

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

  const link = ({ isActive }) =>
    `conversation-item admin-link ${isActive ? "active" : ""}`;

  return (
    <div className="chat-screen">
      {open && <div className="sidebar-overlay no-print" onClick={() => setOpen(false)} />}

      <aside className={`sidebar no-print ${open ? "open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand-mark small">A</div>
          <span className="brand-name">AfyaBora Admin</span>
        </div>

        <nav className="admin-nav">
          <NavLink to="/admin" end className={link} onClick={() => setOpen(false)}>
            Dashboard
          </NavLink>
          <NavLink to="/admin/reset" className={link} onClick={() => setOpen(false)}>
            Reset authenticator
          </NavLink>
          <NavLink to="/admin/admins" className={link} onClick={() => setOpen(false)}>
            Administrators
          </NavLink>
          <NavLink to="/admin/security" className={link} onClick={() => setOpen(false)}>
            Security
          </NavLink>
          <NavLink to="/admin/profile" className={link} onClick={() => setOpen(false)}>
            Profile
          </NavLink>
        </nav>

        <div className="sidebar-user">
          <span>{user.username}</span>
          <button className="btn-text" onClick={logout}>Log out</button>
        </div>
      </aside>

      <main className="chat-main admin-main">
        <header className="chat-topbar no-print">
          <button
            className="icon-btn menu-btn"
            onClick={() => setOpen(true)}
            aria-label="Open menu"
          >
            ☰
          </button>
          <span className="chat-title">{TITLES[pathname] || "Admin"}</span>
        </header>

        <div className="admin-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}