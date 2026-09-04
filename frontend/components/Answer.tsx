import Blueprint from "./Blueprint";
import { citedClauses } from "@/lib/cited";
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

  // **"근거" 와 "검색된 것" 을 가른다.** 예전에는 검색 상위 k 를 통째로
  // "근거 조항" 이라고 불렀는데, 답변이 실제로 인용하는 것은 보통 한둘이다.
  // 더 나쁜 경우도 있었다 — 답변이 "찾지 못했습니다" 인데 아래에 "근거
  // 조항" 일곱 개가 붙었다. 근거가 아닌 것을 근거라고 부르면 그 자체가
  // 뒷받침 없는 문장이다.
  const { cited, fabricated } = citedClauses(
    result.answer,
    clauses.map((h) => h.clause_code).filter((c): c is string => c !== null)
  );
  const 인용된 = clauses.filter((h) => h.clause_code !== null && cited.includes(h.clause_code));
  const 연관 = clauses.filter((h) => h.clause_code === null || !cited.includes(h.clause_code));

  return (
    <>
      <Blueprint className="card" style={{ padding: 24, gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span className="tag tag-accent">{result.persona.name}</span>
          <span className="tag tag-neutral">{result.persona.department}</span>
          <span className="tag tag-neutral">등급 {result.persona.clearance}</span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11.5, color: "var(--color-neutral-600)" }}>
            {/* hits 는 그대로 둔다 — "개수가 권한을 누출하지 않는다" 는 주장이
                이 값에 걸려 있다. 인용·연관으로 나누는 기준은 답변이지 권한이
                아니고 둘의 합은 여전히 조항 수로 고정이라, 나눠도 새지 않는다. */}
            tool_calls {result.tool_calls} · hits {result.hits.length} · 인용 {인용된.length} ·
            연관 {연관.length} ·{" "}
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

      {fabricated.length > 0 && (
        // 답변이 인용했는데 검색 결과에 없는 코드. 모델이 지어낸 인용이다.
        // README 가 "Faithfulness 는 LLM 심판이 아니라 조항 코드의 실재
        // 여부로 잰다" 고 적어둔 그 방식의 1단계다 — 인용이 그 조항 내용과
        // 맞는지까지는 여전히 검사하지 않는다.
        <Blueprint
          className="card"
          role="alert"
          style={{ padding: 18, gap: 8, borderColor: "var(--color-accent-700)" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span className="tag tag-outline">지어낸 인용</span>
            {fabricated.map((c) => (
              <span key={c} className="tag tag-outline">
                {c}
              </span>
            ))}
          </div>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: "var(--color-neutral-800)" }}>
            답변이 인용한 이 조항은 <strong>검색 결과에 없습니다.</strong> 모델이 만들어 낸 번호이므로
            그 부분은 근거가 없습니다 — 아래 목록에 있는 것만 실제로 검색된 조항입니다.
          </p>
        </Blueprint>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>인용한 조항 / Cited</h2>
          <span style={{ fontSize: 12, color: "var(--color-neutral-800)" }}>
            답변 본문이 실제로 가리킨 것
          </span>
        </div>
        {인용된.length === 0 ? (
          // 답변이 아무것도 인용하지 않은 경우. 예전에는 이 상황에서도
          // 검색 결과 전부가 "근거 조항" 이라는 제목 아래 붙어, 답변의
          // "찾지 못했습니다" 와 정면으로 어긋났다.
          <Blueprint className="card" style={{ padding: 18 }}>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: "var(--color-neutral-800)" }}>
              {clauses.length === 0
                ? "이 계정 권한 안에서 관련 조항을 찾지 못했습니다 — 걸러진 흔적이 아니라 검색 결과 자체가 비어 있다는 뜻입니다."
                : "답변이 인용한 조항이 없습니다. 아래는 질의와 가까워 검색된 자료일 뿐, 답변의 근거로 쓰이지는 않았습니다."}
            </p>
          </Blueprint>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 18 }}>
            {인용된.map((h, i) => (
              <조항카드 key={h.chunk_id} 번호={i + 1} hit={h} />
            ))}
          </div>
        )}
      </div>

      {연관.length > 0 && (
        <details>
          <summary
            style={{
              cursor: "pointer",
              fontSize: 15,
              fontWeight: 600,
              color: "var(--color-neutral-900)",
              padding: "6px 0",
            }}
          >
            연관 자료 / Related {연관.length}건
          </summary>
          <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 12 }}>
            <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-800)" }}>
              질의와 가까운 순서로 검색됐지만 답변이 인용하지 않은 자료입니다. 순서가 곧 순위이고
              (RRF 점수는 노출하지 않습니다), 이 목록에 있다는 것은 <strong>이 계정 권한 안에서
              검색됐다</strong>는 뜻이지 답의 근거라는 뜻이 아닙니다.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 18 }}>
              {연관.map((h, i) => (
                <조항카드 key={h.chunk_id} 번호={i + 1} hit={h} />
              ))}
            </div>
          </div>
        </details>
      )}

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
function 조항카드({ 번호, hit }: { 번호: number; hit: FoldedHit }) {
  return (
    <Blueprint className="card" style={{ padding: 18, gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="card-kicker">#{번호}</span>
        <span className="tag tag-outline">{hit.clause_code ?? "조항 밖"}</span>
      </div>
      <div className="card-title">{hit.doc_title}</div>
      <p className="card-body" style={{ lineHeight: 1.6 }}>
        {hit.text}
      </p>
      <div className="card-meta">
        chunk_id {hit.chunk_id}
        {hit.chunkCount > 1 ? ` · 청크 ${hit.chunkCount}개` : ""}
      </div>
    </Blueprint>
  );
}


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
