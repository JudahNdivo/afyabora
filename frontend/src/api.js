// small wrapper for calls to the Flask API
// only a 401 on the stored token logs the user out; network
// problems, server errors and wrong codes keep the session
export async function api(path, { method = "GET", body, auth = true, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  const bearer = token || (auth ? localStorage.getItem("access_token") : null);
  if (bearer) headers.Authorization = `Bearer ${bearer}`;

  let res;
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Could not reach the server, please try again");
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // no JSON body
  }

  if (res.status === 401 && auth && !token) {
    localStorage.clear();
    window.location.href = "/";
  }
  if (!res.ok) {
    throw new Error((data && data.error) || "Something went wrong");
  }
  return data;
}

// POST that reads an answer as it is written. The server sends one JSON
// object per line: pieces of text go to onEvent, and the final "done"
// object is returned. An "error" line, or a stream that ends without
// "done", throws, so a half-finished answer is never treated as complete.
export async function apiStream(path, { body, onEvent } = {}) {
  const headers = { "Content-Type": "application/json" };
  const bearer = localStorage.getItem("access_token");
  if (bearer) headers.Authorization = `Bearer ${bearer}`;

  let res;
  try {
    res = await fetch(path, {
      method: "POST",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Could not reach the server, please try again");
  }

  if (res.status === 401) {
    localStorage.clear();
    window.location.href = "/";
  }
  if (!res.ok) {
    let data = null;
    try {
      data = await res.json();
    } catch {
      // no JSON body
    }
    throw new Error((data && data.error) || "Something went wrong");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done = null;

  try {
    while (true) {
      const { value, done: finished } = await reader.read();
      if (finished) break;
      buffer += decoder.decode(value, { stream: true });

      let newline;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (!line) continue;

        const event = JSON.parse(line);
        if (event.type === "error") throw new Error(event.error);
        if (event.type === "done") done = event;
        else if (onEvent) onEvent(event);
      }
    }
  } catch (err) {
    if (err.name === "TypeError") throw new Error("The connection was lost, please try again");
    throw err;
  }

  if (!done) throw new Error("The answer was cut off, please try again");
  return done;
}