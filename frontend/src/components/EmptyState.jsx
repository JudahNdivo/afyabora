const STARTERS = [
  {
    label: "English",
    questions: [
      "How is HIV transmitted?",
      "What are the symptoms of syphilis?",
      "How is chlamydia treated?",
    ],
  },
  {
    label: "Kiswahili",
    questions: [
      "Naweza kuambukizwa VVU aje?",
      "Dalili za kaswende ni zipi?",
      "Matibabu ya klamidia ni gani?",
    ],
  },
];

export default function EmptyState({ onPick }) {
  return (
    <div className="empty-state">
      <div className="brand-mark">A</div>
      <h2>How can I help?</h2>
      <p>
        Ask about HIV, syphilis, gonorrhoea, chlamydia or HPV, in English or
        Kiswahili. Answers are based on WHO, CDC and Kenyan health guidelines.
      </p>

      {STARTERS.map((group) => (
        <div key={group.label} className="starter-group">
          <span className="starter-label">{group.label}</span>
          <div className="starter-list">
            {group.questions.map((q) => (
              <button key={q} className="starter" onClick={() => onPick(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}