"use client";

import { useState } from "react";
import Blueprint from "./Blueprint";
import type { Principal } from "./PersonaSegment";
import type { AskResult } from "./Answer";

const SAMPLES = [
  "임원 성과급은 어떤 기준으로 정해지나",
  "운영 서버에 접속하려면 어떤 승인이 필요한가",
  "비밀번호는 얼마나 자주 바꿔야 하나",
];

type CompareRow = { hitCount: number; codes: string[] } | "error";

export default function RightRail({
  personas,
  query,
  onSelectSample,
}: {
  personas: Principal[] | null;
  query: string;
  onSelectSample: (text: string) => void;
}) {
  const [comparing, setComparing] = useState(false);
  const [results, setResults] = useState<Record<string, CompareRow> | null>(null);

  // 목업은 페르소나별 요약을 목 데이터로 미리 그렸다. 그 값은 세 번 묻지
  // 않고는 알 수 없으므로, 여기서는 버튼을 눌렀을 때만 실제로 세 번 묻는다.
  async function compare() {
    if (!personas || !query.trim() || comparing) return;
    setComparing(true);
    const next: Record<string, CompareRow> = {};
    setResults(next);
    for (const p of personas) {
      try {
        const r = await fetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, persona: p.name }),
        });
        if (!r.ok) throw new Error(String(r.status));
        const data = (await r.json()) as AskResult;
        const codes = [...new Set(data.hits.map((h) => h.clause_code).filter((c): c is string => c !== null))];
        next[p.name] = { hitCount: data.hits.length, codes };
      } catch {
        next[p.name] = "error";
      }
      setResults({ ...next });
    }
    setComparing(false);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Blueprint className="card" style={{ padding: 18, gap: 12 }}>
        <div className="card-kicker">같은 질문 · 세 계정</div>
        <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-700)" }}>
          버튼을 누르면 지금 입력한 질의를 세 계정으로 실제로 물어 hits 개수와 조항 코드를 비교합니다.
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={compare}
            disabled={!personas || !query.trim() || comparing}
          >
            {comparing ? "비교 중…" : "세 계정으로 비교"}
          </button>
          <span style={{ fontSize: 11, color: "var(--color-neutral-600)" }}>질의 3회를 사용합니다</span>
        </div>
        {results && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {personas?.map((p) => {
              const row = results[p.name];
              return (
                <div
                  key={p.name}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "9px 11px",
                    border: "1px solid var(--color-divider)",
                    fontSize: 12.5,
                  }}
                >
                  <span>{p.name}</span>
                  <span style={{ color: "var(--color-neutral-600)" }}>
                    {!row
                      ? "대기 중…"
                      : row === "error"
                        ? "오류"
                        : `${row.hitCount}건 · ${row.codes.length ? row.codes.join(", ") : "조항 없음"}`}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </Blueprint>

      <Blueprint className="card" style={{ padding: 18, gap: 10 }}>
        <div className="card-kicker">예시 질의</div>
        {SAMPLES.map((s) => (
          <button
            key={s}
            type="button"
            className="btn btn-secondary"
            style={{
              justifyContent: "flex-start",
              textAlign: "left",
              fontSize: 12.5,
              height: "auto",
              padding: "9px 11px",
              whiteSpace: "normal",
            }}
            onClick={() => onSelectSample(s)}
          >
            {s}
          </button>
        ))}
      </Blueprint>
    </div>
  );
}
