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

// small helper so every API call automatically includes the auth token.
// Returns the parsed JSON, or null if the request failed. Only a 401
// (token rejected) logs the user out; network problems and server
// errors keep the session so the user can simply try again.
async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
        ...options.headers
      }
    });
  } catch (err) {
    return null;
  }

  if (res.status === 401) {
    localStorage.clear();
    window.location.href = "/";
    return null;
  }

  if (!res.ok) {
    return null;
  }

  try {
    return await res.json();
  } catch (err) {
    return null;
  }
}

// shows a failure message in the chat area as an assistant bubble
function showErrorBubble(text) {
  const el = document.createElement("div");
  el.className = "message assistant";
  el.textContent = text;
  messageList.appendChild(el);
  messageList.scrollTop = messageList.scrollHeight;
}

async function loadConversations() {
  // keep the current list if the request fails
  conversations = (await api("/api/conversations")) || conversations;
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

  const result = await api(`/api/conversations/${id}`, { method: "DELETE" });
  if (!result) {
    alert("Could not delete the conversation, please try again.");
    return;
  }

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
  const messages = await api(`/api/conversations/${id}/messages`);
  if (!messages) {
    alert("Could not open the conversation, please try again.");
    return;
  }

  currentConversationId = id;
  renderConversationList(conversations);

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

  // reload the whole conversation from the server either way, so the
  // screen matches what was actually saved
  await openConversation(currentConversationId);

  if (!result || !result.answer) {
    showErrorBubble("Something went wrong and your edit was not applied. Please try again.");
  }
}

document.getElementById("new-chat-btn").addEventListener("click", async () => {
  const conv = await api("/api/conversations", { method: "POST" });
  if (!conv) {
    alert("Could not start a new chat, please try again.");
    return;
  }
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
  } else {
    // the request failed: take the unsent bubble back, put the text back
    // in the box so it can be resent, and say what happened
    pendingUserBubble.remove();
    messageInput.value = text;
    showErrorBubble("Something went wrong and your message did not go through. Please try sending it again.");
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