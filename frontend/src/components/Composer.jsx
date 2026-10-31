import { useState } from "react";

export default function Composer({ onSend, disabled }) {
  const [text, setText] = useState("");

  async function submit(e) {
    e.preventDefault();
    const message = text.trim();
    if (!message || disabled) return;

    setText("");
    const ok = await onSend(message);
    // put the text back if it did not go through, so it can be resent
    if (!ok) setText(message);
  }

  return (
    <form className="message-form" onSubmit={submit}>
      <div className="message-form-row">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask in English or Kiswahili..."
          aria-label="Your question"
        />
        <button
          type="submit"
          className="btn-send"
          disabled={disabled || !text.trim()}
          aria-label="Send"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 19V5M12 5l-6 6M12 5l6 6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      <p className="composer-note">
        AfyaBora shares general health information, not medical advice.
      </p>
    </form>
  );
}