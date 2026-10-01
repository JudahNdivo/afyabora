// Supabase's password recovery email links here with session info in
// the URL hash fragment, e.g. #access_token=...&type=recovery
const hashParams = new URLSearchParams(window.location.hash.slice(1));
const accessToken = hashParams.get("access_token");
const type = hashParams.get("type");

const form = document.getElementById("reset-form");
const invalidLinkEl = document.getElementById("invalid-link");
const errorEl = document.getElementById("form-error");
const submitBtn = document.getElementById("submit-btn");

if (!accessToken || type !== "recovery") {
  form.hidden = true;
  invalidLinkEl.hidden = false;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.hidden = true;

  const newPassword = document.getElementById("new-password").value;
  const confirmPassword = document.getElementById("confirm-password").value;

  if (newPassword !== confirmPassword) {
    errorEl.textContent = "Passwords do not match";
    errorEl.hidden = false;
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Updating...";

  try {
    const res = await fetch("/api/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token: accessToken, new_password: newPassword })
    });
    const data = await res.json();

    if (!res.ok) throw new Error(data.error || "Failed to update password");

    alert("Password updated! Please log in with your new password.");
    window.location.href = "/";
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Update password";
  }
});