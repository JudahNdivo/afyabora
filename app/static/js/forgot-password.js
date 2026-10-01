const form = document.getElementById("forgot-form");
const errorEl = document.getElementById("form-error");
const successEl = document.getElementById("form-success");
const submitBtn = document.getElementById("submit-btn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.hidden = true;
  successEl.hidden = true;

  const email = document.getElementById("email").value;

  submitBtn.disabled = true;
  submitBtn.textContent = "Sending...";

  try {
    const res = await fetch("/api/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
    const data = await res.json();

    if (!res.ok) throw new Error(data.error || "Something went wrong");

    successEl.textContent = data.message;
    successEl.hidden = false;
    form.reset();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Send reset link";
  }
});