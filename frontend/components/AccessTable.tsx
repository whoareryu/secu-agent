"use client";

import { useEffect, useState } from "react";
import Blueprint from "./Blueprint";
import { LOG_LIMIT } from "@/lib/types";

// GET /api/access-log 가 돌려주는 행 그대로 — backend AccessRecordView.
// 문서 제목·본문은 기록에 없다(Task 1 의 결정). AlertTable.tsx 도 같은 형태를
// 쓴다.
export type AccessRecord = {
  ts: string;
  persona: string;
  department: string;
  clearance: number;
  query: string;
  clause_code: string | null;
  // 열람 대상은 청크이거나 로그 이벤트다. 두 id 공간은 겹치므로 숫자만으로는
  // 무엇을 가리키는지 알 수 없다 — 종류를 함께 받아 함께 보여준다.
  resource_kind: "chunk" | "log_event";
  resource_id: number;
  allowed: boolean;
};

export function formatResource(r: Pick<AccessRecord, "resource_kind" | "resource_id">): string {
  return `${r.resource_kind === "log_event" ? "로그 이벤트" : "청크"} ${r.resource_id}`;
}

export function formatTs(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const okStyle: React.CSSProperties = {
  fontSize: 12,
  color: "var(--color-accent-800)",
  border: "1px solid var(--color-accent)",
  padding: "2px 9px",
};
const blockedStyle: React.CSSProperties = {
  fontSize: 12,
  color: "var(--color-accent-900)",
  background: "var(--color-accent-200)",
  padding: "2px 9px",
};

const chipBase: React.CSSProperties = {
  padding: "7px 13px",
  background: "transparent",
  border: 0,
  borderRight: "1px solid var(--color-divider)",
  fontSize: 12.5,
  cursor: "pointer",
  color: "var(--color-text)",
  fontFamily: "var(--font-body)",
};
const chipOn: React.CSSProperties = { ...chipBase, background: "var(--color-accent-700)", color: "var(--color-bg)" };

// 필터 칩은 프로토타입 그대로(전체 / 차단만 / 페르소나별)지만 페르소나 이름은
// 기록에서 뽑는다 — 계정을 하드코딩하지 않는다.
export default function AccessTable() {
  const [records, setRecords] = useState<AccessRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("전체");

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/access-log?limit=${LOG_LIMIT}`)
      .then((r) => {
        if (!r.ok) throw new Error(`access-log ${r.status}`);
        return r.json() as Promise<AccessRecord[]>;
      })
      .then((data) => {
        if (!cancelled) setRecords(data);
      })
      .catch(() => {
        if (!cancelled) setError("열람 이력을 불러오지 못했습니다");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <p style={{ fontSize: 13, color: "var(--color-accent-700)" }}>{error}</p>;
  }
  if (!records) {
    return <p style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>불러오는 중…</p>;
  }

  const personas = Array.from(new Set(records.map((r) => r.persona)));
  const filters = ["전체", "차단만", ...personas];
  const rows =
    filter === "전체"
      ? records
      : filter === "차단만"
        ? records.filter((r) => !r.allowed)
        : records.filter((r) => r.persona === filter);

  return (
    <Blueprint className="card" style={{ padding: 22, gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div className="card-kicker">Access log</div>
          <div style={{ fontFamily: "var(--font-heading)", fontSize: 21, marginTop: 2 }}>직원별 서류 열람 이력</div>
        </div>
        <span style={{ flex: 1 }} />
        <div style={{ display: "flex", border: "1px solid var(--color-divider)" }}>
          {filters.map((f) => (
            <button
              key={f}
              type="button"
              // 선택 상태를 색으로만 전달하면 보조기술에는 같은 버튼 셋으로 들린다.
              aria-pressed={f === filter}
              onClick={() => setFilter(f)}
              style={f === filter ? chipOn : chipBase}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      {/* table-scroll: 질의 컬럼이 자유 텍스트라 좁은 화면에서 표가 카드보다
          넓어질 수 있다 — 표를 반응형으로 접지는 않되(범위 밖), 그 넓어짐이
          페이지 자체를 가로로 밀지 않게 여기서 가둔다(app/_ds/industry.css). */}
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>시각</th>
              <th>페르소나</th>
              <th>부서·등급</th>
              <th style={{ width: "26%" }}>질의</th>
              <th>조항</th>
              <th style={{ textAlign: "right" }}>결과</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  style={{ padding: "40px 0", textAlign: "center", color: "var(--color-neutral-600)", fontSize: 13.5 }}
                >
                  아직 기록이 없습니다. 질의를 하면 여기에 쌓입니다.
                </td>
              </tr>
            ) : (
              rows.map((r, i) => (
                <tr key={`${r.ts}-${r.resource_kind}-${r.resource_id}-${i}`}>
                  <td style={{ fontSize: 12.5, color: "var(--color-neutral-600)", whiteSpace: "nowrap" }}>
                    {formatTs(r.ts)}
                  </td>
                  <td style={{ fontSize: 14.5 }}>{r.persona}</td>
                  <td style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>
                    {r.department} · 등급 {r.clearance}
                  </td>
                  <td style={{ fontSize: 13 }}>{r.query}</td>
                  <td>
                    <span className="tag tag-neutral">{r.clause_code ?? "—"}</span>
                    <div style={{ fontSize: 11, color: "var(--color-neutral-600)", marginTop: 2 }}>
                      {formatResource(r)}
                    </div>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <span style={r.allowed ? okStyle : blockedStyle}>{r.allowed ? "정상 열람" : "차단"}</span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 12.5, color: "var(--color-neutral-600)" }}>
        {/* 받은 행이 상한과 같으면 그 위에 더 있을 수 있다. "전체" 라고 적으면
            거짓이 된다 — 실제로 일어난 요청만 보여준다고 밝힌 화면이다. */}
        표시 {rows.length}건 · {records.length >= LOG_LIMIT ? `최근 ${LOG_LIMIT}건` : `전체 ${records.length}건`}
      </div>
    </Blueprint>
  );
}
