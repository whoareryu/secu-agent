"use client";

import Blueprint from "./Blueprint";
import type { Principal } from "./PersonaSegment";

const currentStyleOn: React.CSSProperties = {
  fontSize: 12,
  color: "var(--color-accent-800)",
  border: "1px solid var(--color-accent)",
  padding: "2px 9px",
};

// GET /api/principals 그대로. "직급" 컬럼은 뺐다 — principals 테이블에
// 그런 컬럼이 없다. 없는 값을 지어내지 않는다.
export default function PrincipalTable({ principals, current }: { principals: Principal[]; current: string }) {
  return (
    <Blueprint className="card" style={{ padding: 20 }}>
      <table className="table">
        <thead>
          <tr>
            <th>이름 / Name</th>
            <th>부서 / Department</th>
            <th>등급 / Clearance</th>
            <th style={{ textAlign: "right" }}>현재 선택</th>
          </tr>
        </thead>
        <tbody>
          {principals.map((p) => (
            <tr key={p.name}>
              <td style={{ fontSize: 15 }}>{p.name}</td>
              <td>{p.department}</td>
              <td>등급 {p.clearance}</td>
              <td style={{ textAlign: "right" }}>
                {p.name === current ? (
                  <span style={currentStyleOn}>선택됨</span>
                ) : (
                  <span style={{ color: "var(--color-neutral-500)" }}>—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Blueprint>
  );
}
