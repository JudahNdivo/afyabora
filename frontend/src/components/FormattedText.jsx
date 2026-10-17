// shows a plain-text answer as paragraphs and bullet lists
export default function FormattedText({ text }) {
  const blocks = [];
  let list = [];
  let para = [];

  function flushList() {
    if (list.length) blocks.push({ type: "list", items: list });
    list = [];
  }
  function flushPara() {
    if (para.length) blocks.push({ type: "p", text: para.join(" ") });
    para = [];
  }

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) {
      flushList();
      flushPara();
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      flushPara();
      list.push(line.slice(2));
    } else {
      flushList();
      para.push(line);
    }
  }
  flushList();
  flushPara();

  return blocks.map((b, i) =>
    b.type === "list" ? (
      <ul key={i}>
        {b.items.map((item, j) => <li key={j}>{item}</li>)}
      </ul>
    ) : (
      <p key={i}>{b.text}</p>
    )
  );
}