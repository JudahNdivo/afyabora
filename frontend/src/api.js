// small wrapper for calls to the Flask API
// only a 401 (token rejected) logs the user out; network
// problems and server errors keep the session
export async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = localStorage.getItem("access_token");
    if (token) headers.Authorization = `Bearer ${token}`;
  }

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

  if (res.status === 401 && auth) {
    localStorage.clear();
    window.location.href = "/";
  }
  if (!res.ok) {
    throw new Error((data && data.error) || "Something went wrong");
  }
  return data;
}