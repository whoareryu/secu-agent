"use client";

import Blueprint from "./Blueprint";
import type { Principal } from "./PersonaSegment";

// GET /api/documents 가 돌려주는 형태 그대로 — 권한 필터 없이 전부.
export type Document = {
  id: number;
  title: string;
  doc_type: string;
  required_clearance: number;
  allowed_departments: string[];
  source_path: string;
  chunk_count: number;
};

// backend/core/access/visibility.py 의 규칙과 같아야 한다 — SQL(chunk_search.
// _권한_WHERE) · 파이썬(visibility.py)에 이은 세 번째 사본. 허용 부서가
// 비어 있으면 전사 공개다("아무도 못 본다"가 아니다).
export function visible(d: Document, p: Principal): boolean {
  return (
    d.required_clearance <= p.clearance &&
    (d.allowed_departments.length === 0 || d.allowed_departments.includes(p.department))
  );
}

const visStyleOn: React.CSSProperties = {
  fontSize: 12,
  color: "var(--color-accent-800)",
  border: "1px solid var(--color-accent)",
  padding: "2px 9px",
};
const visStyleOff: React.CSSProperties = {
  fontSize: 12,
  color: "var(--color-neutral-500)",
  border: "1px dashed var(--color-neutral-400)",
  padding: "2px 9px",
};

export default function DocumentTable({ documents, persona }: { documents: Document[]; persona: Principal }) {
  return (
    <Blueprint className="card" style={{ padding: 20 }}>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: "34%" }}>문서 / Document</th>
            <th>유형</th>
            <th>필요 등급</th>
            <th>허용 부서</th>
            <th>source_path</th>
            <th style={{ textAlign: "right" }}>가시성</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((d) => {
            const vis = visible(d, persona);
            return (
              <tr key={d.id}>
                <td style={{ fontSize: 14.5 }}>{d.title}</td>
                <td>
                  <span className="tag tag-neutral">{d.doc_type}</span>
                </td>
                <td>{d.required_clearance}</td>
                <td style={{ color: "var(--color-neutral-700)" }}>
                  {d.allowed_departments.length ? d.allowed_departments.join(", ") : "전사 공개"}
                </td>
                <td style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>{d.source_path}</td>
                <td style={{ textAlign: "right" }}>
                  <span style={vis ? visStyleOn : visStyleOff}>{vis ? "보임" : "가려짐"}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Blueprint>
  );
}
