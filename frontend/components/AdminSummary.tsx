"use client";

import { useEffect, useState } from "react";
import Blueprint from "./Blueprint";
import type { AccessRecord } from "./AccessTable";

// 요약 4칸은 실제 기록에서 계산한다 — 프로토타입의 342 / 128 / 17 은 목이었다.
// 기간 필터가 없어서 "이번 주"라고 쓰지 않는다.
export default function AdminSummary() {
  const [records, setRecords] = useState<AccessRecord[] | null>(null);
  const [violations, setViolations] = useState<AccessRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch("/api/access-log?limit=200").then((r) => {
        if (!r.ok) throw new Error(`access-log ${r.status}`);
        return r.json() as Promise<AccessRecord[]>;
      }),
      fetch("/api/access-log?violations=1&limit=200").then((r) => {
        if (!r.ok) throw new Error(`violations ${r.status}`);
        return r.json() as Promise<AccessRecord[]>;
      }),
    ])
      .then(([log, v]) => {
        if (cancelled) return;
        setRecords(log);
        setViolations(v);
      })
      .catch(() => {
        if (!cancelled) setError("요약을 불러오지 못했습니다");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <p style={{ fontSize: 13, color: "var(--color-accent-700)" }}>{error}</p>;
  }
  if (!records || !violations) {
    return <p style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>불러오는 중…</p>;
  }

  // 질의 수: 고유 (query, persona, 시각) 조합 수. 열람된 서류: 고유 chunk_id
  // 수. 확인 필요 알림은 차단된 요청과 같다 — 확인 상태를 저장하는 곳이 없다.
  const queryCount = new Set(records.map((r) => `${r.query}|${r.persona}|${r.ts}`)).size;
  const chunkCount = new Set(records.map((r) => r.chunk_id)).size;
  const blockedCount = violations.length;
  const needsReview = violations.length;

  const tiles: { label: string; value: number; note: string; accent?: boolean }[] = [
    { label: "질의 수", value: queryCount, note: "기록 전체" },
    { label: "열람된 서류", value: chunkCount, note: "조항 단위 열람 건수" },
    { label: "차단된 요청", value: blockedCount, note: "권한 밖 문서 요청" },
    { label: "확인 필요 알림", value: needsReview, note: "차단된 요청과 동일", accent: needsReview > 0 },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 18 }}>
        {tiles.map((t) => (
          <Blueprint
            key={t.label}
            className="card"
            style={
              t.accent
                ? { padding: 20, gap: 6, borderColor: "var(--color-accent-700)", background: "var(--color-accent-100)" }
                : { padding: 20, gap: 6 }
            }
          >
            <div className="card-kicker">{t.label}</div>
            <div style={{ fontFamily: "var(--font-heading)", fontSize: 44, lineHeight: 1, letterSpacing: "-.01em" }}>
              {t.value}
            </div>
            <div style={{ fontSize: 11.5, color: "var(--color-neutral-600)" }}>{t.note}</div>
          </Blueprint>
        ))}
      </div>
      {records.length === 0 && (
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-neutral-600)" }}>
          아직 기록이 없습니다. 질의를 하면 여기에 쌓입니다.
        </p>
      )}
    </div>
  );
}
