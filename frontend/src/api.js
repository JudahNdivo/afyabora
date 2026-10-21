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