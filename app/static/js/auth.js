// Toggle between login and signup without reloading the page
const tabs = document.querySelectorAll(".auth-tab");
const usernameField = document.getElementById("username-field");
const submitBtn = document.getElementById("submit-btn");
const form = document.getElementById("auth-form");
const errorEl = document.getElementById("form-error");

let mode = "login";

tabs.forEach(tab => {
  tab.addEventListener("click", () => {
    tabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    mode = tab.dataset.mode;

    const isSignup = mode === "signup";
    usernameField.hidden = !isSignup;
    document.getElementById("username").required = isSignup;
    submitBtn.textContent = isSignup ? "Sign up" : "Log in";
    errorEl.hidden = true;
  });
});

function validatePassword(password) {
  const errors = [];

  if (password.length < 8) {
    errors.push("at least 8 characters");
  }
  if (!/[A-Z]/.test(password)) {
    errors.push("one uppercase letter");
  }
  if (!/[a-z]/.test(password)) {
    errors.push("one lowercase letter");
  }
  if (!/[0-9]/.test(password)) {
    errors.push("one number");
  }

  return errors;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.hidden = true;

  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  if (mode === "signup") {
    const passwordErrors = validatePassword(password);
    if (passwordErrors.length > 0) {
      errorEl.textContent = `Password needs: ${passwordErrors.join(", ")}`;
      errorEl.hidden = false;
      return;
    }
  }

  try {
    if (mode === "signup") {
      const username = document.getElementById("username").value;

      const res = await fetch("/api/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, username })
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || "Signup failed");

      // After signup, log in immediately so the user isn't asked twice
      await doLogin(email, password);
    } else {
      await doLogin(email, password);
    }
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
});

async function doLogin(email, password) {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();

  if (!res.ok) throw new Error(data.error || "Login failed");

  // store the token and user info so the chat page can use them
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("user", JSON.stringify(data.user));

  window.location.href = "/chat";
}