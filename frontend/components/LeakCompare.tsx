"use client";

import { useEffect, useState } from "react";
import Blueprint from "./Blueprint";
import type { CompareResponse, DemoPersonaView } from "@/lib/types";

// Task 2 Step 4 에서 확인하고 통제자가 2026-09-02 에 이 작업 코퍼스로
// 재현한 질의. 셋이 갈라져 사전/사후 필터링의 차이가 눈에 보인다.
const 기본_질의 = "임원 성과급은 어떤 기준으로 정해지나";
const K = 10;

// 이 목록의 첫 원소는 위의 기본_질의 — **갈라지는** 쪽이다. 나머지 셋은
// 순진한 경로가 이번에는 새지 *않는* 예시다. 실측(2026-09-02, 작업 코퍼스,
// k=10, 사전→사후):
//   기본_질의            김개발 10→7 · 박인사 10→7 · 최임원 10→10
//   나머지 세 질의       세 계정 모두 10→10
// 갈리는 것과 갈리지 않는 것을 한 줄에 섞어 두는 것이 요점이다 — 눌러 보면
// 어떤 질의는 갈라지고 어떤 질의는 갈라지지 않는다. 이 목록이 하는 일은
// 값을 대신 보여주는 것이 아니라 눌러볼 자리를 가리키는 것뿐이다.
// 화면의 숫자는 항상 이번 호출의 실제 응답에서 온다.
const 예시_질의 = [
  기본_질의,
  "비밀번호는 얼마나 자주 바꿔야 하나",
  "이사회 의사록 열람 절차",
  "네트워크 접근 통제 정책",
];

// `required` 는 빈 문자열만 막는다. 공백만 넣고 제출하면 run() 이 조용히 조기
// 반환하고, 입력창은 한 질의를 보여주는데 아래 숫자들은 **다른 질의**의 것이
// 그대로 남는다 — 뒷받침 없는 것을 한 줄도 두지 않는다는 이 화면의 규칙을
// 정면으로 어긴다. 브라우저가 제출 자체를 막게 해서 그 상태가 생기지 않게 한다.
const 공백만_금지 = ".*\\S.*";

type Status = "idle" | "loading" | "done" | "error";
type Path = "prefiltered" | "naive";

// 조항 코드를 접어서 보여준다 (Answer.tsx 의 foldByClause 와 같은 이유 —
// 같은 조항이 여러 청크로 쪼개져 있으면 목록이 그 청크 수만큼 반복된다).
function 조항_묶기(codes: string[]): { code: string; count: number }[] {
  const folded: { code: string; count: number }[] = [];
  const indexByCode = new Map<string, number>();
  for (const code of codes) {
    const i = indexByCode.get(code);
    if (i === undefined) {
      indexByCode.set(code, folded.length);
      folded.push({ code, count: 1 });
    } else {
      folded[i].count += 1;
    }
  }
  return folded;
}

export default function LeakCompare() {
  const [query, setQuery] = useState(기본_질의);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [path, setPath] = useState<Path>("prefiltered");
  const [coldStart, setColdStart] = useState(false);

  // AskPanel.tsx 와 같은 장치를 같은 이유로 둔다 — 컨테이너가 잠들어 있었으면
  // e5 임베딩 모델을 올리느라 수십 초 걸리고, /demo/compare 도 /ask 와 같은
  // api/deps.py 의 `_자원()` lru_cache 를 지난다. 이 화면은 클릭을 기다리지
  // 않고 마운트 즉시 부르므로 그 콜드 스타트를 가장 먼저 맞는 자리다.
  useEffect(() => {
    if (status !== "loading") {
      setColdStart(false);
      return;
    }
    const timer = setTimeout(() => setColdStart(true), 8000);
    return () => clearTimeout(timer);
  }, [status]);

  async function run(q: string) {
    if (!q.trim()) return;
    setStatus("loading");
    // 실패했을 때 이전 값이 남아 있으면 로딩이 성공으로 끝난 것처럼
    // 보인다 — 먼저 비워서 화면에 지어낸 값이 남지 않게 한다.
    setResult(null);
    setPath("prefiltered");
    try {
      const r = await fetch("/api/demo-compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, k: K }),
      });
      if (!r.ok) {
        const body: { error?: string } | null = await r.json().catch(() => null);
        setErrorMsg(body?.error ?? `요청이 실패했습니다 (${r.status})`);
        setStatus("error");
        return;
      }
      setResult((await r.json()) as CompareResponse);
      setStatus("done");
    } catch {
      setErrorMsg("백엔드에 닿지 못했습니다");
      setStatus("error");
    }
  }

  // 마운트 시 기본 질의로 한 번 부른다 — 패널이 "라이브"라고 배지에 적어
  // 두고 실제로는 클릭을 기다리기만 하면 그 배지가 거짓이 된다.
  useEffect(() => {
    run(기본_질의);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    run(query);
  }

  const 갈림 = (result?.personas ?? []).map((p: DemoPersonaView) => ({
    ...p,
    diff: p.prefiltered.count - p.naive.count,
  }));
  const 모두_동일 = 갈림.length > 0 && 갈림.every((p) => p.diff === 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <form onSubmit={submit} style={{ display: "flex", gap: 10 }}>
        <input
          className="input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="질의를 입력하세요"
          required
          pattern={공백만_금지}
          title="공백만으로는 비교할 수 없습니다"
          maxLength={500}
          style={{ flex: 1, height: 40, fontSize: 14 }}
        />
        <button
          type="submit"
          className="btn btn-primary"
          style={{ height: 40, minWidth: 88 }}
          disabled={status === "loading"}
        >
          {status === "loading" ? "비교 중…" : "비교"}
        </button>
      </form>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {예시_질의.map((q) => (
          <button
            key={q}
            type="button"
            className="btn btn-secondary"
            style={{ height: 30, fontSize: 12, padding: "0 10px" }}
            disabled={status === "loading"}
            onClick={() => {
              setQuery(q);
              run(q);
            }}
          >
            {q}
          </button>
        ))}
      </div>

      {status === "loading" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--color-neutral-600)" }}>
            세 계정 × 두 경로, 여섯 번 검색합니다. 임베딩은 한 번만 계산하고 LLM 은 부르지 않습니다.
          </p>
          {coldStart && (
            <p style={{ margin: 0, fontSize: 12.5, color: "var(--color-accent-700)" }}>
              백엔드가 잠들어 있었다면 임베딩 모델을 올리는 중입니다. 첫 요청만 수십 초 걸립니다.
            </p>
          )}
        </div>
      )}

      {status === "error" && (
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-accent-700)" }}>실패: {errorMsg}</p>
      )}

      {status === "done" && result && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span className="tag tag-outline">k={result.k}</span>
            <span style={{ flex: 1 }} />
            <button
              type="button"
              className="btn btn-secondary"
              style={{ height: 30, fontSize: 12.5 }}
              onClick={() => setPath(path === "prefiltered" ? "naive" : "prefiltered")}
            >
              {path === "prefiltered" ? "순진한 방식으로 다시" : "사전 필터링으로 되돌리기"}
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}>
            {result.personas.map((p) => {
              const 경로 = p[path];
              return (
                <Blueprint key={p.name} className="card" style={{ padding: 16, gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span className="tag tag-accent">{p.name}</span>
                    <span className="tag tag-neutral">등급 {p.clearance}</span>
                  </div>
                  <div style={{ fontFamily: "var(--font-heading)", fontSize: 28 }}>{경로.count}건</div>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {조항_묶기(경로.clause_codes).map(({ code, count }) => (
                      <span key={code} className="tag tag-outline" style={{ fontSize: 11 }}>
                        {code}
                        {count > 1 ? ` ×${count}` : ""}
                      </span>
                    ))}
                  </div>
                </Blueprint>
              );
            })}
          </div>

          {path === "prefiltered" ? (
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
              사전 필터링에서 개수를 정하는 것은 k 입니다 — 볼 수 있는 청크가 k 이상이면 언제나 정확히 k 이고,
              그보다 적을 때만 그 수만큼입니다. 어느 쪽이든 권한 밖에 무엇이 있는지에 따라서는 변하지 않습니다 —
              그것이 개수 채널이 막혔다는 뜻입니다.
            </p>
          ) : 모두_동일 ? (
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-accent-700)" }}>
              사후 필터링(순진한 경로)에서는 개수가 권한 범위의 크기를 그대로 드러냅니다 — 이 질의에서는 세 계정의
              개수가 같아 그 크기 차이가 드러나지 않았을 뿐입니다. 안전하다는 뜻이 아닙니다. 코드도 취약점도
              그대로이고, 이 질의가 권한 밖 내용에 가깝지 않아 이번에는 보이지 않은 것뿐입니다 — 누출은 없는 것이
              아니라 보이지 않는 것입니다.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
                사후 필터링(순진한 경로)에서는 개수가 권한 범위의 크기를 그대로 드러냅니다.
              </p>
              {갈림
                .filter((p) => p.diff > 0)
                .map((p) => (
                  <p key={p.name} style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "var(--color-accent-700)" }}>
                    {p.name}: {p.prefiltered.count} → {p.naive.count} — {p.diff}건이 사라졌습니다. 그 {p.diff}가 곧
                    &quot;여기 이 사람이 못 보는 문서가 있다&quot;는 신호입니다.
                  </p>
                ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
