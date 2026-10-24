import { useState } from "react";

export default function Sidebar({
  conversations, currentId, username, open,
  onClose, onNewChat, onSelect, onDelete, onLogout, onProfile,
}) {
  const [query, setQuery] = useState("");

  // search only looks at conversation titles
  const shown = conversations.filter((c) =>
    c.title.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <>
      {open && <div className="sidebar-overlay" onClick={onClose} />}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand-mark small">A</div>
          <span className="brand-name">AfyaBora</span>
        </div>

        <button className="btn-new-chat" onClick={onNewChat}>+ New chat</button>

        <input
          className="search-input"
          placeholder="Search conversations..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <div className="conversation-list">
          {shown.map((c) => (
            <div
              key={c.id}
              className={`conversation-item ${c.id === currentId ? "active" : ""}`}
              onClick={() => onSelect(c.id)}
            >
              <span className="conversation-title">{c.title}</span>
              <button
                className="conversation-delete-btn"
                title="Delete conversation"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(c.id);
                }}
              >
                ×
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar-user">
          <span>{username}</span>
          <span>
            <button className="btn-text" onClick={onProfile}>Profile</button>
            <button className="btn-text" onClick={onLogout}>Log out</button>
          </span>
        </div>
      </aside>
    </>
  );
}