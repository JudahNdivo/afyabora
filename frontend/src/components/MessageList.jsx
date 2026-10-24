import { useEffect, useRef, useState } from "react";
import FormattedText from "./FormattedText";

function UserMessage({ message, onEdit }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  function startEdit() {
    setDraft(message.content);
    setEditing(true);
  }

  function handleKey(e) {
    if (e.key === "Escape") setEditing(false);
    if (e.key === "Enter") {
      const text = draft.trim();
      setEditing(false);
      if (text && text !== message.content) onEdit(message.id, text);
    }
  }

  return (
    <div className="message-wrapper user">
      {editing ? (
        <>
          <input
            className="message-edit-input"
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKey}
          />
          <span className="edit-hint">Enter to send, Esc to cancel</span>
        </>
      ) : (
        <>
          <div className="message user">{message.content}</div>
          {message.id !== "pending" && (
            <button className="message-edit-btn" onClick={startEdit}>Edit</button>
          )}
        </>
      )}
    </div>
  );
}

export default function MessageList({ messages, loading, onEdit }) {
  const endRef = useRef(null);

  // keep the newest message in view; while an answer is being written the
  // scroll jumps instead of animating, so it does not lag behind the text
  useEffect(() => {
    const writing = messages[messages.length - 1]?.id === "streaming";
    endRef.current?.scrollIntoView({ behavior: writing ? "auto" : "smooth" });
  }, [messages, loading]);

  return (
    <div className="message-list">
      {messages.map((m) =>
        m.role === "user" ? (
          <UserMessage key={m.id} message={m} onEdit={onEdit} />
        ) : (
          <div key={m.id} className="message-wrapper assistant">
            <div className="message assistant">
              <FormattedText text={m.content} />
            </div>
          </div>
        )
      )}

      {loading && (
        <div className="loading-indicator">
          <span /><span /><span />
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}