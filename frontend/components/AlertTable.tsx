"use client";

import { useEffect, useState } from "react";
import Blueprint from "./Blueprint";
import { formatResource, formatTs, type AccessRecord } from "./AccessTable";
import { LOG_LIMIT } from "@/lib/types";

// GET /api/access-log?violations=1 — AccessViolation 이 실제로 발생했을 때만
// 행이 생긴다(지금은 비어 있는 게 정상 상태다). "처리 상태" 컬럼은 없다 —
// 확인 여부를 저장하는 곳이 없어서, 있으면 그 값도 지어낸 값이 된다. 프로토
// 타입의 "사유" 컬럼도 없다 — 이 엔드포인트는 사유 텍스트를 담지 않는다.
// 대신 실제로 있는 질의 내용을 보여준다.
export default function AlertTable() {
  const [records, setRecords] = useState<AccessRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/access-log?violations=1&limit=${LOG_LIMIT}`)
      .then((r) => {
        if (!r.ok) throw new Error(`violations ${r.status}`);
        return r.json() as Promise<AccessRecord[]>;
      })
      .then((data) => {
        if (!cancelled) setRecords(data);
      })
      .catch(() => {
        if (!cancelled) setError("권한 밖 열람 알림을 불러오지 못했습니다");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Blueprint className="card" style={{ padding: 22, gap: 14, borderColor: "var(--color-accent-700)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span className="tag tag-outline">확인 필요 / Needs review</span>
        <span style={{ fontFamily: "var(--font-heading)", fontSize: 21 }}>권한 밖 열람 알림</span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
          {records && records.length >= LOG_LIMIT ? `최근 ${LOG_LIMIT}건` : `기록 전체 · ${records ? records.length : 0}건`}
        </span>
      </div>
      {error ? (
        <p style={{ fontSize: 13, color: "var(--color-accent-700)" }}>{error}</p>
      ) : !records ? (
        <p style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>불러오는 중…</p>
      ) : (
        <div className="table-scroll">
          {/* table-scroll: AccessTable 과 같은 모양이다 — 질의 열이 자유
              텍스트라 좁은 화면에서 표가 카드보다 넓어진다. 그 스크롤을
              표 안에 가둔다. */}
          <table className="table">
          <thead>
            <tr>
              <th>발생 시각</th>
              <th>직원</th>
              <th>대상</th>
              <th>질의</th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  style={{ padding: "40px 0", textAlign: "center", color: "var(--color-neutral-600)", fontSize: 13.5 }}
                >
                  권한 밖 열람이 기록되지 않았습니다.
                </td>
              </tr>
            ) : (
              records.map((r, i) => (
                <tr key={`${r.ts}-${r.resource_kind}-${r.resource_id}-${i}`}>
                  <td style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>{formatTs(r.ts)}</td>
                  <td style={{ fontSize: 14.5 }}>
                    {r.persona}
                    <span style={{ color: "var(--color-neutral-600)", fontSize: 12.5 }}>
                      {" "}
                      · {r.department} · 등급 {r.clearance}
                    </span>
                  </td>
                  <td style={{ fontSize: 13 }}>
                    {formatResource(r)}
                    {r.clause_code ? ` · ${r.clause_code}` : ""}
                  </td>
                  <td style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>{r.query}</td>
                </tr>
              ))
            )}
          </tbody>
          </table>
        </div>
      )}
      <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-700)" }}>
        알림에는 식별자만 담고 문서 본문·제목은 담지 않습니다.
      </p>
    </Blueprint>
  );
}
