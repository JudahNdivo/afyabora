// Redirect to login if there's no token - this page requires auth
const token = localStorage.getItem("access_token");
const user = JSON.parse(localStorage.getItem("user") || "null");

if (!token || !user) {
  window.location.href = "/";
}

document.getElementById("username-display").textContent = user.username;

let conversations = [];
let currentConversationId = null;

const conversationList = document.getElementById("conversation-list");
const messageList = document.getElementById("message-list");
const emptyState = document.getElementById("empty-state");
const messageForm = document.getElementById("message-form");
const messageInput = document.getElementById("message-input");
const loadingIndicator = document.getElementById("loading-indicator");

// small helper so every API call automatically includes the auth token
async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
      ...options.headers
    }
  });

  if (res.status === 401) {
    // token expired or invalid - send back to login
    localStorage.clear();
    window.location.href = "/";
    return;
  }

  return res.json();
}

async function loadConversations() {
  conversations = await api("/api/conversations");
  renderConversationList(conversations);
}

function renderConversationList(list) {
  conversationList.innerHTML = "";
  list.forEach(conv => {
    const item = document.createElement("div");
    item.className = "conversation-item";
    if (conv.id === currentConversationId) item.classList.add("active");

    const title = document.createElement("span");
    title.className = "conversation-title";
    title.textContent = conv.title;
    title.addEventListener("click", () => openConversation(conv.id));

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "conversation-delete-btn";
    deleteBtn.textContent = "×";
    deleteBtn.title = "Delete conversation";
    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteConversation(conv.id);
    });

    item.appendChild(title);
    item.appendChild(deleteBtn);
    conversationList.appendChild(item);
  });
}

async function deleteConversation(id) {
  const confirmed = confirm("Delete this conversation? This cannot be undone.");
  if (!confirmed) return;

  await api(`/api/conversations/${id}`, { method: "DELETE" });

  conversations = conversations.filter(c => c.id !== id);
  renderConversationList(conversations);

  // if the deleted conversation was open, go back to the empty state
  if (currentConversationId === id) {
    currentConversationId = null;
    messageList.hidden = true;
    messageForm.hidden = true;
    emptyState.hidden = false;
  }
}

async function openConversation(id) {
  currentConversationId = id;
  renderConversationList(conversations);

  const messages = await api(`/api/conversations/${id}/messages`);

  emptyState.hidden = true;
  messageList.hidden = false;
  messageForm.hidden = false;

  messageList.innerHTML = "";
  messages.forEach(msg => appendMessage(msg.role, msg.content, msg.id));
  messageList.scrollTop = messageList.scrollHeight;
}

// returns the created wrapper element, so the caller can retroactively
// attach an id/edit button once the server confirms the message was saved
function appendMessage(role, content, messageId = null) {
  const wrapper = document.createElement("div");
  wrapper.className = `message-wrapper ${role}`;

  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.textContent = content;
  wrapper.appendChild(el);

  // only user messages are editable, and only once they have a real
  // id (a message that hasn't been saved yet has no id to edit)
  if (role === "user" && messageId) {
    addEditButton(wrapper, el, messageId, content);
  }

  messageList.appendChild(wrapper);
  return wrapper;
}

function addEditButton(wrapper, messageEl, messageId, content) {
  const editBtn = document.createElement("button");
  editBtn.className = "message-edit-btn";
  editBtn.textContent = "Edit";
  editBtn.addEventListener("click", () => startEditingMessage(wrapper, messageEl, messageId, content));
  wrapper.appendChild(editBtn);
}

function startEditingMessage(wrapper, messageEl, messageId, originalContent) {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "message-edit-input";
  input.value = originalContent;

  wrapper.replaceChild(input, messageEl);
  input.focus();

  input.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      const newText = input.value.trim();
      if (!newText || newText === originalContent) {
        // nothing changed, just restore the normal view
        wrapper.replaceChild(messageEl, input);
        return;
      }
      await submitMessageEdit(messageId, newText);
    }
    if (e.key === "Escape") {
      wrapper.replaceChild(messageEl, input);
    }
  });
}

async function submitMessageEdit(messageId, newText) {
  loadingIndicator.hidden = false;

  const result = await api(
    `/api/conversations/${currentConversationId}/messages/${messageId}`,
    { method: "PUT", body: JSON.stringify({ message: newText }) }
  );

  loadingIndicator.hidden = true;

  if (result && result.answer) {
    // simplest safe approach: reload the whole conversation from the
    // server, rather than trying to patch the DOM in place
    await openConversation(currentConversationId);
  }
}

document.getElementById("new-chat-btn").addEventListener("click", async () => {
  const conv = await api("/api/conversations", { method: "POST" });
  conversations.unshift(conv);
  await openConversation(conv.id);
});

messageForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text || !currentConversationId) return;

  // no id yet - the server will give us one once this message is saved
  const pendingUserBubble = appendMessage("user", text);
  messageInput.value = "";
  messageList.scrollTop = messageList.scrollHeight;

  loadingIndicator.hidden = false;

  const result = await api(`/api/conversations/${currentConversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message: text })
  });

  loadingIndicator.hidden = true;

  if (result && result.answer) {
    // retroactively make the user bubble we already showed editable,
    // now that we know its real database id
    if (result.user_message_id) {
      const bubble = pendingUserBubble.querySelector(".message");
      addEditButton(pendingUserBubble, bubble, result.user_message_id, text);
    }

    appendMessage("assistant", result.answer, result.assistant_message_id);
    messageList.scrollTop = messageList.scrollHeight;

    // refresh the sidebar in case the title just got set from this message
    await loadConversations();
    renderConversationList(conversations);
  }
});

// client-side filter over already-loaded conversation titles.
// NOTE: this only searches titles, not full message content - a
// proper search-by-content endpoint isn't built yet (future work)
document.getElementById("search-input").addEventListener("input", (e) => {
  const query = e.target.value.toLowerCase();
  const filtered = conversations.filter(c =>
    c.title.toLowerCase().includes(query)
  );
  renderConversationList(filtered);
});

document.getElementById("logout-btn").addEventListener("click", () => {
  localStorage.clear();
  window.location.href = "/";
});

loadConversations();