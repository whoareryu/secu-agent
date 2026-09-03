"use client";

import { useEffect, useState } from "react";
import Blueprint from "./Blueprint";
import type { AccessRecord } from "./AccessTable";
import { LOG_LIMIT } from "@/lib/types";

// 요약 4칸은 실제 기록에서 계산한다 — 프로토타입의 342 / 128 / 17 은 목이었다.
// 기간 필터가 없어서 "이번 주"라고 쓰지 않는다.
export default function AdminSummary() {
  const [records, setRecords] = useState<AccessRecord[] | null>(null);
  const [violations, setViolations] = useState<AccessRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch(`/api/access-log?limit=${LOG_LIMIT}`).then((r) => {
        if (!r.ok) throw new Error(`access-log ${r.status}`);
        return r.json() as Promise<AccessRecord[]>;
      }),
      fetch(`/api/access-log?violations=1&limit=${LOG_LIMIT}`).then((r) => {
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

  // 질의 수: 고유 (query, persona, 시각) 조합 수. 열람된 서류: 고유 청크 수 —
  // 기록에는 로그 이벤트 열람도 섞이므로 종류로 먼저 거른다. 거르지 않으면
  // 겹치는 id 때문에 "서류" 수가 로그 건수와 뒤섞인다.
  // 확인 필요 알림은 차단된 요청과 같다 — 확인 상태를 저장하는 곳이 없다.
  const queryCount = new Set(records.map((r) => `${r.query}|${r.persona}|${r.ts}`)).size;
  const chunkCount = new Set(
    records.filter((r) => r.resource_kind === "chunk").map((r) => r.resource_id),
  ).size;
  const blockedCount = violations.length;
  const needsReview = violations.length;

  // 백엔드 limit 상한이 LOG_LIMIT 이라 그만큼만 받는다. 정확히 그 수를
  // 받았다면 그 위에 더 있을 수 있고, 그러면 이 타일들은 전체가 아니라
  // 최근 LOG_LIMIT 건이라는 표본 위에서 계산된 값이다. 그것을 화면이
  // 말하지 않으면 숫자가 상한에 고정된 채 "전체" 인 척한다.
  const 기록_잘림 = records.length >= LOG_LIMIT;
  const 위반_잘림 = violations.length >= LOG_LIMIT;
  const 표본 = (잘림: boolean, 전체설명: string) =>
    잘림 ? `최근 ${LOG_LIMIT}건 기준` : 전체설명;

  const tiles: { label: string; value: number; note: string; accent?: boolean }[] = [
    { label: "질의 수", value: queryCount, note: 표본(기록_잘림, "기록 전체") },
    { label: "열람된 서류", value: chunkCount, note: 표본(기록_잘림, "조항 단위 열람 건수") },
    { label: "차단된 요청", value: blockedCount, note: 표본(위반_잘림, "권한 밖 열람 요청") },
    {
      label: "확인 필요 알림",
      value: needsReview,
      note: 표본(위반_잘림, "차단된 요청과 동일"),
      accent: needsReview > 0,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))", gap: 18 }}>
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
      {(기록_잘림 || 위반_잘림) && (
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--color-neutral-600)" }}>
          기록이 {LOG_LIMIT}건 상한에 닿았습니다. 위 숫자는 최근 {LOG_LIMIT}건 위에서 계산한 값이며 그 이전 기록은
          포함되지 않습니다.
        </p>
      )}
      {records.length === 0 && (
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-neutral-600)" }}>
          아직 기록이 없습니다. 질의를 하면 여기에 쌓입니다.
        </p>
      )}
    </div>
  );
}
