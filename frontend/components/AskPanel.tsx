"use client";

import { useEffect, useState } from "react";
import Blueprint from "./Blueprint";
import PersonaSegment, { type Principal } from "./PersonaSegment";
import Answer, { type AskResult } from "./Answer";

type Status = "idle" | "loading" | "done" | "error";
type ErrorKind = "401" | "429" | "other";

export default function AskPanel({
  personas,
  personasError,
  query,
  onQueryChange,
  persona,
  onPersonaChange,
}: {
  personas: Principal[] | null;
  personasError: string | null;
  query: string;
  onQueryChange: (v: string) => void;
  persona: string;
  onPersonaChange: (v: string) => void;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<AskResult | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [errorKind, setErrorKind] = useState<ErrorKind>("other");
  const [coldStart, setColdStart] = useState(false);

  // 프로토타입의 로딩 상태는 1.2초를 가정한다. 실제로는 컨테이너가 잠들어
  // 있었으면 임베딩 모델을 올리느라 수십 초 걸린다 — 8초를 넘기면 그 사실을
  // 알린다.
  useEffect(() => {
    if (status !== "loading") {
      setColdStart(false);
      return;
    }
    const timer = setTimeout(() => setColdStart(true), 8000);
    return () => clearTimeout(timer);
  }, [status]);

  async function ask() {
    if (!query.trim() || !persona) return;
    setStatus("loading");
    const start = performance.now();
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, persona }),
      });
      const ms = performance.now() - start;
      if (!r.ok) {
        setElapsedMs(ms);
        setErrorKind(r.status === 401 ? "401" : r.status === 429 ? "429" : "other");
        setStatus("error");
        return;
      }
      const data = (await r.json()) as AskResult;
      setElapsedMs(ms);
      setResult(data);
      setStatus("done");
    } catch {
      setElapsedMs(performance.now() - start);
      setErrorKind("other");
      setStatus("error");
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    ask();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, minWidth: 0 }}>
      <style>{"@keyframes sa-pulse{0%,100%{opacity:.25}50%{opacity:.7}}"}</style>

      <Blueprint className="card" style={{ padding: 22, gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div className="card-kicker">Persona · 시연 계정</div>
          <span style={{ fontSize: 11.5, color: "var(--color-neutral-600)" }}>POST /ask · persona 이름만 전송</span>
        </div>

        {personasError ? (
          <p style={{ margin: 0, fontSize: 13, color: "var(--color-accent-700)" }}>{personasError}</p>
        ) : !personas ? (
          <p style={{ margin: 0, fontSize: 13, color: "var(--color-neutral-600)" }}>페르소나 불러오는 중…</p>
        ) : (
          <PersonaSegment personas={personas} value={persona} onChange={onPersonaChange} />
        )}

        <form onSubmit={submit} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            <input
              className="input"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder="규정에 대해 질문하세요"
              required
              maxLength={500}
              style={{ height: 42, fontSize: 15 }}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            style={{ height: 42, minWidth: 104 }}
            disabled={status === "loading" || !persona}
          >
            {status === "loading" ? "질의 중…" : "질의 / Ask"}
          </button>
        </form>
        <div style={{ fontSize: 12, color: "var(--color-neutral-600)", lineHeight: 1.5 }}>
          부서·등급은 시연을 위해 선택하는 값이지만, 선택된 값이 실제 권한 필터(사전 필터링 WHERE 절)를 그대로
          탑니다.
        </div>
      </Blueprint>

      {status === "loading" && (
        <Blueprint className="card" style={{ padding: 22, gap: 14 }}>
          <div className="card-kicker">Running</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div
              style={{
                height: 12,
                width: "62%",
                background: "var(--color-neutral-300)",
                animation: "sa-pulse 1.1s ease-in-out infinite",
              }}
            />
            <div
              style={{
                height: 12,
                width: "88%",
                background: "var(--color-neutral-300)",
                animation: "sa-pulse 1.1s ease-in-out .15s infinite",
              }}
            />
            <div
              style={{
                height: 12,
                width: "40%",
                background: "var(--color-neutral-300)",
                animation: "sa-pulse 1.1s ease-in-out .3s infinite",
              }}
            />
          </div>
          <div style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
            에이전트가 search_policy 도구를 호출하는 중입니다. 스트리밍하지 않고 완성된 응답을 한 번에 받습니다.
          </div>
          {coldStart && (
            <div style={{ fontSize: 12, color: "var(--color-accent-700)" }}>
              백엔드가 잠들어 있었다면 모델을 올리는 중입니다. 첫 요청만 수십 초 걸립니다.
            </div>
          )}
        </Blueprint>
      )}

      {status === "error" && errorKind === "401" && (
        <Blueprint className="card" style={{ padding: 22, gap: 12, borderColor: "var(--color-accent-700)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="tag tag-outline">401</span>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: 19 }}>세션이 만료되었습니다</span>
          </div>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: "var(--color-neutral-700)" }}>
            다시 로그인한 뒤 질의를 다시 보내주세요.
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <a className="btn btn-secondary" href="/">
              다시 로그인
            </a>
          </div>
        </Blueprint>
      )}

      {status === "error" && errorKind === "429" && (
        <Blueprint className="card" style={{ padding: 22, gap: 12, borderColor: "var(--color-accent-700)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="tag tag-outline">429</span>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: 19 }}>
              오늘 사용 가능한 질의를 모두 썼습니다
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: "var(--color-neutral-700)" }}>
            내일 다시 시도해주세요.
          </p>
        </Blueprint>
      )}

      {status === "error" && errorKind === "other" && (
        <Blueprint className="card" style={{ padding: 22, gap: 12, borderColor: "var(--color-accent-700)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="tag tag-outline">502</span>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: 19 }}>
              백엔드에 닿지 못했습니다 / Upstream unavailable
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: "var(--color-neutral-700)" }}>
            Route Handler 가 Cloudflare 컨테이너 호출에 실패했습니다. 어떤 페르소나가 존재하는지, 어떤 문서가
            있는지는 오류 메시지에 담기지 않습니다 — 예외 본문이 누출 경로가 되지 않도록 chunk_id 외에는 싣지
            않습니다.
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-secondary" onClick={ask}>
              다시 시도 / Retry
            </button>
          </div>
        </Blueprint>
      )}

      {status === "done" && result && <Answer result={result} elapsedMs={elapsedMs} />}
    </div>
  );
}
