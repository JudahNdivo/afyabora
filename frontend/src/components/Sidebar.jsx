import { useState } from "react";

export default function Sidebar({
  conversations, currentId, username, open,
  onClose, onNewChat, onSelect, onDelete, onRename, onLogout, onProfile,
}) {
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState("");
  // the open three-dot menu: which chat, and where on the screen
  const [menu, setMenu] = useState(null);

  // search only looks at conversation titles
  const shown = conversations.filter((c) =>
    c.title.toLowerCase().includes(query.toLowerCase())
  );

  function openMenu(e, c) {
    e.stopPropagation();
    // the menu is placed from the button's position so the scrolling
    // list cannot cut it off
    const box = e.currentTarget.getBoundingClientRect();
    setMenu({ id: c.id, title: c.title, top: box.bottom + 4, left: box.right - 140 });
  }

  function startEdit() {
    setEditingId(menu.id);
    setDraft(menu.title);
    setMenu(null);
  }

  // an empty or unchanged title is ignored
  function saveEdit(c) {
    const title = draft.trim();
    setEditingId(null);
    if (title && title !== c.title) onRename(c.id, title);
  }

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
              onClick={() => editingId !== c.id && onSelect(c.id)}
            >
              {editingId === c.id ? (
                <input
                  className="conversation-rename-input"
                  value={draft}
                  maxLength={80}
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={() => saveEdit(c)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveEdit(c);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                />
              ) : (
                <span className="conversation-title">{c.title}</span>
              )}

              {editingId !== c.id && (
                <button
                  className="conversation-menu-btn"
                  title="More options"
                  aria-label="More options"
                  onClick={(e) => openMenu(e, c)}
                >
                  ⋮
                </button>
              )}
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

      {menu && (
        <>
          <div className="conversation-menu-backdrop" onClick={() => setMenu(null)} />
          <div className="conversation-menu" style={{ top: menu.top, left: menu.left }}>
            <button onClick={startEdit}>Rename</button>
            <button
              className="danger"
              onClick={() => {
                const id = menu.id;
                setMenu(null);
                onDelete(id);
              }}
            >
              Delete
            </button>
          </div>
        </>
      )}
    </>
  );
}