import Blueprint from "./Blueprint";

type Hit = { chunk_id: number; clause_code: string | null; doc_title: string; text: string };
export type AskResult = {
  answer: string;
  hits: Hit[];
  persona: { name: string; department: string; clearance: number };
  tool_calls: number;
  remaining: number | null;
  log_scope?: string | null;
};

type FoldedHit = Hit & { chunkCount: number };

// 조항 코드로 중복을 접는다 (Ruling W3b-R5). hits[] 자체는 이 함수 밖에서
// 그대로 유지된다 — 개수가 권한을 누출하지 않는다는 주장이 hits.length 에
// 걸려 있기 때문에, 접는 것은 이 표시용 배열뿐이다. clause_code 가 null 인
// 항목(조항 밖 텍스트)은 접지 않고 각각 별개로 둔다.
function foldByClause(hits: Hit[]): FoldedHit[] {
  const folded: FoldedHit[] = [];
  const indexByCode = new Map<string, number>();
  for (const h of hits) {
    if (h.clause_code === null) {
      folded.push({ ...h, chunkCount: 1 });
      continue;
    }
    const existingIndex = indexByCode.get(h.clause_code);
    if (existingIndex === undefined) {
      indexByCode.set(h.clause_code, folded.length);
      folded.push({ ...h, chunkCount: 1 });
    } else {
      folded[existingIndex].chunkCount += 1;
    }
  }
  return folded;
}

export default function Answer({ result, elapsedMs }: { result: AskResult; elapsedMs: number }) {
  const clauses = foldByClause(result.hits);

  return (
    <>
      <Blueprint className="card" style={{ padding: 24, gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span className="tag tag-accent">{result.persona.name}</span>
          <span className="tag tag-neutral">{result.persona.department}</span>
          <span className="tag tag-neutral">등급 {result.persona.clearance}</span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11.5, color: "var(--color-neutral-600)" }}>
            tool_calls {result.tool_calls} · hits {result.hits.length} · 조항 {clauses.length} ·{" "}
            {Math.round(elapsedMs)}ms
          </span>
        </div>
        <div
          style={{
            fontFamily: "var(--font-heading)",
            fontSize: 13,
            letterSpacing: ".16em",
            textTransform: "uppercase",
            color: "var(--color-accent)",
          }}
        >
          Answer
        </div>
        <p style={{ margin: 0, fontSize: 15.5, lineHeight: 1.72, textWrap: "pretty", whiteSpace: "pre-wrap" }}>
          {result.answer}
        </p>
        {result.log_scope && (
          <p style={{
            margin: "10px 0 0",
            fontSize: 12.5,
            lineHeight: 1.6,
            color: "var(--color-neutral-700)",
            borderLeft: "2px solid var(--color-accent-400)",
            paddingLeft: 10,
          }}>
            {result.log_scope}
          </p>
        )}
      </Blueprint>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>근거 조항 / Cited clauses</h2>
          <span style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
            hits[] · 순서가 곧 순위입니다 (RRF 점수는 노출하지 않습니다)
          </span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 18 }}>
          {clauses.map((h, i) => (
            <Blueprint key={h.chunk_id} className="card" style={{ padding: 18, gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span className="card-kicker">#{i + 1}</span>
                <span className="tag tag-outline">{h.clause_code ?? "조항 밖"}</span>
              </div>
              <div className="card-title">{h.doc_title}</div>
              <p className="card-body" style={{ lineHeight: 1.6 }}>
                {h.text}
              </p>
              <div className="card-meta">
                chunk_id {h.chunk_id}
                {h.chunkCount > 1 ? ` · 청크 ${h.chunkCount}개` : ""}
              </div>
            </Blueprint>
          ))}
        </div>
      </div>

      <Blueprint className="card" style={{ padding: 20, gap: 10, background: "var(--color-accent-100)" }}>
        <div className="card-kicker">Pre-filtering</div>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--color-accent-900)" }}>
          권한 검사는 검색 <strong>이전</strong>에 SQL WHERE 절로 일어납니다. 권한을 통과한 문서 안에서 상위 k
          건을 고르므로, 각 계정에 허용된 조항이 k 건 이상 있는 한 세 계정 모두 같은 개수의 결과를 받습니다 —{" "}
          <strong>개수가 등급에 따라 갈리지 않고, 숨겨진 문서는 순위의 빈자리로도 드러나지 않습니다.</strong>{" "}
          허용된 조항이 k 건에 못 미치면 그보다 적게 받지만, 그것은 그 계정이 볼 수 있는 것을 다 본 결과이지 무언가가
          걸러진 흔적이 아닙니다. 사후 필터링이라면 &quot;3건만 남았다&quot;는 사실 자체가 숨겨진 문서의 신호가
          됩니다.
        </p>
      </Blueprint>
    </>
  );
}
