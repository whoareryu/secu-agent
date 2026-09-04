import Blueprint from "./Blueprint";
import { parseBlocks, type Span } from "@/lib/answer-format";

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
        <div className="card-kicker">답변 / Answer</div>
        <AnswerBody text={result.answer} />
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
        {clauses.length === 0 && (
          // 0건이면 제목과 캡션만 남고 아래가 완전한 공백이었다. 이 화면에서는
          // 특히 나쁘다 — 아래 Pre-filtering 설명이 "허용된 조항이 k 건에
          // 못 미치면 그보다 적게 받는다" 고 적어 두는데, 정확히 그 상황에서
          // 화면이 아무 말도 하지 않으면 "고장났나" 와 "내 권한 안에 없구나"
          // 를 구별할 수 없다.
          <Blueprint className="card" style={{ padding: 18 }}>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: "var(--color-neutral-800)" }}>
              이 계정 권한 안에서 관련 조항을 찾지 못했습니다 — 걸러진 흔적이
              아니라 검색 결과 자체가 비어 있다는 뜻입니다.
            </p>
          </Blueprint>
        )}
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
          건을 고르므로, 각 계정에 허용된 조항이 k 건 이상 있는 한 모든 계정이 같은 개수의 결과를 받습니다 —{" "}
          <strong>개수가 등급에 따라 갈리지 않고, 숨겨진 문서는 순위의 빈자리로도 드러나지 않습니다.</strong>{" "}
          허용된 조항이 k 건에 못 미치면 그보다 적게 받지만, 그것은 그 계정이 볼 수 있는 것을 다 본 결과이지 무언가가
          걸러진 흔적이 아닙니다. 사후 필터링이라면 &quot;3건만 남았다&quot;는 사실 자체가 숨겨진 문서의 신호가
          됩니다.
        </p>
      </Blueprint>
    </>
  );
}

function Spans({ spans }: { spans: Span[] }) {
  return (
    <>
      {spans.map((s, i) =>
        s.t === "b" ? (
          <strong key={i} style={{ fontWeight: 700, color: "var(--color-text)" }}>{s.v}</strong>
        ) : s.t === "code" ? (
          <code key={i} style={{
            fontFamily: "var(--font-mono)", fontSize: ".9em", letterSpacing: 0,
            background: "var(--color-neutral-200)", padding: "1px 5px", borderRadius: 5,
          }}>{s.v}</code>
        ) : (
          <span key={i}>{s.v}</span>
        )
      )}
    </>
  );
}

// LLM 은 마크다운으로 답한다. 그대로 뿌리면 `* **[4.2.2] ...**:` 가
// 기호째 보인다(2026-09-03 화면 확인). 파싱은 lib/answer-format.ts 가 하고
// 여기서는 그리기만 한다.
function AnswerBody({ text }: { text: string }) {
  const blocks = parseBlocks(text);
  const 본문 = { margin: 0, fontSize: 15.5, lineHeight: 1.75, color: "var(--color-neutral-900)" } as const;
  // parseBlocks("") 는 빈 배열이다(lib/answer-format.test.ts 가 고정한다).
  // 그대로 두면 "답변 / Answer" 키커 아래가 빈 상자로 남아, 모델이 아무것도
  // 돌려주지 않은 것과 화면이 못 그린 것이 같아 보인다.
  if (blocks.length === 0) {
    return (
      <p style={{ ...본문, color: "var(--color-neutral-800)" }}>
        모델이 빈 답변을 돌려줬습니다. 아래 근거 조항은 실제로 검색된 것입니다.
      </p>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {blocks.map((b, i) => {
        if (b.kind === "hr") return <hr key={i} className="hr" style={{ margin: "4px 0" }} />;
        if (b.kind === "h")
          return (
            <div key={i} style={{ fontSize: 16.5, fontWeight: 700, letterSpacing: "-.02em", marginTop: i ? 6 : 0 }}>
              <Spans spans={b.spans} />
            </div>
          );
        if (b.kind === "p")
          return (
            <p key={i} style={{ ...본문, textWrap: "pretty" }}>
              <Spans spans={b.spans} />
            </p>
          );
        const Tag = b.kind === "ol" ? "ol" : "ul";
        return (
          <Tag key={i} style={{ ...본문, paddingLeft: 22, display: "flex", flexDirection: "column", gap: 6 }}>
            {b.items.map((item, j) => (
              <li key={j}>
                <Spans spans={item} />
              </li>
            ))}
          </Tag>
        );
      })}
    </div>
  );
}
