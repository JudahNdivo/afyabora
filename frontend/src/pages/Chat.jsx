import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import Sidebar from "../components/Sidebar";
import MessageList from "../components/MessageList";
import Composer from "../components/Composer";
import EmptyState from "../components/EmptyState";
import "../styles/chat.css";

export default function Chat() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "null");

  const [conversations, setConversations] = useState([]);
  const [currentId, setCurrentId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // send people without a session back to the login page, then load their chats
  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      navigate("/");
      return;
    }
    api("/api/conversations")
      .then(setConversations)
      .catch((err) => setNotice(err.message));
  }, [navigate]);

  if (!user) return null;

  async function refreshConversations() {
    try {
      setConversations(await api("/api/conversations"));
    } catch {
      // keep the current list
    }
  }

  async function openConversation(id) {
    try {
      const data = await api(`/api/conversations/${id}/messages`);
      setMessages(data);
      setCurrentId(id);
      setSidebarOpen(false);
    } catch (err) {
      setNotice(err.message);
    }
  }

  function selectConversation(id) {
    setNotice("");
    openConversation(id);
  }

  // a new chat is only saved once the first message is sent
  function newChat() {
    setCurrentId(null);
    setMessages([]);
    setNotice("");
    setSidebarOpen(false);
  }

  // returns true if the message went through, so the box can keep the text if not
  async function sendMessage(text) {
    if (sending) return false;
    setSending(true);
    setNotice("");

    // show the question straight away
    setMessages((m) => [...m, { id: "pending", role: "user", content: text }]);

    try {
      let id = currentId;
      if (!id) {
        const conv = await api("/api/conversations", { method: "POST" });
        id = conv.id;
        setCurrentId(id);
        setConversations((c) => [conv, ...c]);
      }

      const result = await api(`/api/conversations/${id}/messages`, {
        method: "POST",
        body: { message: text },
      });

      setMessages((m) => [
        ...m.filter((x) => x.id !== "pending"),
        { id: result.user_message_id, role: "user", content: text },
        { id: result.assistant_message_id, role: "assistant", content: result.answer },
      ]);
      refreshConversations();
      return true;
    } catch {
      setMessages((m) => m.filter((x) => x.id !== "pending"));
      setNotice("Your message did not go through. Please try sending it again.");
      return false;
    } finally {
      setSending(false);
    }
  }

  async function editMessage(messageId, newText) {
    setSending(true);
    setNotice("");
    try {
      await api(`/api/conversations/${currentId}/messages/${messageId}`, {
        method: "PUT",
        body: { message: newText },
      });
    } catch {
      setNotice("Your edit was not applied. Please try again.");
    }
    // reload either way so the screen matches what was saved
    await openConversation(currentId);
    setSending(false);
  }

  async function deleteConversation(id) {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;
    try {
      await api(`/api/conversations/${id}`, { method: "DELETE" });
      setConversations((c) => c.filter((x) => x.id !== id));
      if (id === currentId) {
        setCurrentId(null);
        setMessages([]);
      }
    } catch {
      setNotice("Could not delete the conversation. Please try again.");
    }
  }

  function logout() {
    localStorage.clear();
    navigate("/");
  }

  const title = conversations.find((c) => c.id === currentId)?.title || "New chat";

  return (
    <div className="chat-screen">
      <Sidebar
        conversations={conversations}
        currentId={currentId}
        username={user.username}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={newChat}
        onSelect={selectConversation}
        onDelete={deleteConversation}
        onLogout={logout}
      />

      <main className="chat-main">
        <header className="chat-topbar">
          <button
            className="icon-btn menu-btn"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
          >
            ☰
          </button>
          <span className="chat-title">{title}</span>
        </header>

        {messages.length === 0 && !sending ? (
          <EmptyState onPick={sendMessage} />
        ) : (
          <MessageList messages={messages} loading={sending} onEdit={editMessage} />
        )}

        {notice && <p className="chat-notice">{notice}</p>}
        <Composer onSend={sendMessage} disabled={sending} />
      </main>
    </div>
  );
}