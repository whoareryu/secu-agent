type Hit = { chunk_id: number; clause_code: string | null; doc_title: string; text: string };
export type AskResult = {
  answer: string;
  hits: Hit[];
  persona: { name: string; department: string; clearance: number };
  tool_calls: number;
};

export default function Answer({ result }: { result: AskResult }) {
  return (
    <section style={{ marginTop: 24 }}>
      <h2>답변</h2>
      <p style={{ whiteSpace: "pre-wrap" }}>{result.answer}</p>
      <p style={{ fontSize: 13, color: "#666" }}>
        {result.persona.name} · {result.persona.department} · 등급{" "}
        {result.persona.clearance} · 도구 {result.tool_calls}회
      </p>
      <h3>근거 {result.hits.length}건</h3>
      {result.hits.map((h) => (
        <div key={h.chunk_id} style={{ borderLeft: "3px solid #ddd", paddingLeft: 10, marginBottom: 10 }}>
          <strong>{h.clause_code ? `[${h.clause_code}]` : "[조항 밖]"} {h.doc_title}</strong>
          <p style={{ margin: "4px 0", fontSize: 14 }}>{h.text.slice(0, 300)}</p>
        </div>
      ))}
    </section>
  );
}
