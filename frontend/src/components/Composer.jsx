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
          placeholder="Ask a question in English or Kiswahili..."
        />
        <button type="submit" className="btn-send" disabled={disabled || !text.trim()}>
          Send
        </button>
      </div>
      <p className="composer-note">
        AfyaBora shares general health information, not medical advice.
      </p>
    </form>
  );
}