"use client";

import { useEffect, useState } from "react";
import Blueprint from "./Blueprint";
import Answer, { type AskResult } from "./Answer";

type Status = "idle" | "loading" | "done" | "error";
type ErrorKind = "401" | "429" | "400" | "other";

export default function AskPanel({
  query,
  onQueryChange,
}: {
  query: string;
  onQueryChange: (v: string) => void;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<AskResult | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [errorKind, setErrorKind] = useState<ErrorKind>("other");
  // 배지에 실제 상태 코드를 싣는다. 예전에는 "502" 가 리터럴로 박혀 있어
  // 어떤 실패든 502 로 보였다.
  const [errorStatus, setErrorStatus] = useState(0);
  const [errorDetail, setErrorDetail] = useState("");
  const [coldStart, setColdStart] = useState(false);
  // 알리스트 사용자는 null 로 남아 배지가 뜨지 않는다.
  const [remaining, setRemaining] = useState<number | null>(null);

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
    if (!query.trim()) return;
    setStatus("loading");
    const start = performance.now();
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const ms = performance.now() - start;
      if (!r.ok) {
        setElapsedMs(ms);
        // 400 은 백엔드가 아니라 **이쪽 상태**가 문제라는 뜻이다 — 대개
        // 페르소나 쿠키가 없거나 principals 에서 사라진 이름이다. 이걸
        // "other" 로 접으면 화면이 "백엔드에 닿지 못했습니다(502)" 라는
        // 거짓 진단을 내놓는다(백엔드는 멀쩡하다).
        const body: { error?: string } | null = await r.json().catch(() => null);
        setErrorStatus(r.status);
        setErrorDetail(body?.error ?? "");
        setErrorKind(
          r.status === 401 ? "401" : r.status === 429 ? "429" : r.status === 400 ? "400" : "other"
        );
        setStatus("error");
        return;
      }
      const data = (await r.json()) as AskResult;
      setElapsedMs(ms);
      setResult(data);
      setRemaining(data.remaining);
      setStatus("done");
    } catch {
      setErrorStatus(0);
      setErrorDetail("");
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
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div className="card-kicker">질의</div>
            {remaining !== null && <span className="tag tag-outline">남은 질의 {remaining}회</span>}
          </div>
          <span style={{ fontSize: 11.5, color: "var(--color-neutral-600)" }}>
            POST /api/ask · 본문은 query 뿐 — 페르소나는 쿠키에서 읽습니다
          </span>
        </div>

        <form onSubmit={submit} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            <input
              className="input"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              // placeholder 는 입력을 시작하면 사라진다 — 라벨이 될 수 없다(WCAG 3.3.2).
          aria-label="규정 질의"
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
            disabled={status === "loading"}
          >
            {status === "loading" ? "질의 중…" : "질의 / Ask"}
          </button>
        </form>
        <div style={{ fontSize: 12, color: "var(--color-neutral-600)", lineHeight: 1.5 }}>
          허브에서 고른 부서·등급이 실제 권한 필터(사전 필터링 WHERE 절)를 그대로 탑니다.
        </div>
      </Blueprint>

      {/* 상태 전환을 보조기술에 알리는 유일한 자리다. 스켈레톤이 뛰는 것과
          답변 카드가 DOM 에 꽂히는 것은 눈에만 보이고, 이 화면은 콜드
          스타트에서 수십 초가 걸린다 — 알림이 없으면 스크린리더 사용자는
          끝났는지조차 모른 채 직접 훑어 내려가야 한다.
          영역 자체는 항상 렌더한다. 조건부로 넣으면 브라우저가 새 노드로
          보고 내용을 읽지 않는 경우가 있다. */}
      <p className="sr-only" role="status" aria-live="polite">
        {status === "loading"
          ? coldStart
            ? "답변을 생성하는 중입니다. 백엔드가 모델을 올리는 중이라 수십 초 걸릴 수 있습니다."
            : "답변을 생성하는 중입니다."
          : status === "done" && result
            ? `답변이 도착했습니다. 근거 조항 ${result.hits.length}건.`
            : status === "error"
              ? "질의가 실패했습니다. 아래 오류 내용을 확인하세요."
              : ""}
      </p>

      {status === "loading" && (
        <Blueprint className="card" style={{ padding: 22, gap: 14 }}>
          <div className="card-kicker">질의 중 / Running</div>
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
        <Blueprint className="card" role="alert"
          style={{ padding: 22, gap: 12, borderColor: "var(--color-accent-700)" }}>
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
        <Blueprint className="card" role="alert"
          style={{ padding: 22, gap: 12, borderColor: "var(--color-accent-700)" }}>
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

      {status === "error" && errorKind === "400" && (
        <Blueprint className="card"
          role="alert"
          style={{ padding: 22, gap: 12, borderColor: "var(--color-accent-700)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="tag tag-outline">400</span>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: 19 }}>
              직원을 다시 골라 주세요
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: "var(--color-neutral-800)" }}>
            {errorDetail || "고른 계정을 확인할 수 없습니다. 허브에서 다시 고르면 이어집니다."}
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <a className="btn btn-secondary" href="/">
              허브로 / Hub
            </a>
          </div>
        </Blueprint>
      )}

      {status === "error" && errorKind === "other" && (
        <Blueprint className="card" role="alert"
          style={{ padding: 22, gap: 12, borderColor: "var(--color-accent-700)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="tag tag-outline">{errorStatus || "네트워크"}</span>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: 19 }}>
              백엔드에 닿지 못했습니다 / Upstream unavailable
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: "var(--color-neutral-700)" }}>
            Route Handler 가 Cloudflare 컨테이너 호출에 실패했습니다. 어떤 페르소나가 존재하는지, 어떤 문서가
            있는지는 오류 메시지에 담기지 않습니다 — 예외 본문이 누출 경로가 되지 않도록 식별자 외에는 싣지
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
