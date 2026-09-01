"use client";

import Blueprint from "./Blueprint";
import type { Principal } from "./PersonaSegment";

// GET /api/principals 그대로. 목업에 있던 "직급" 과 "현재 선택" 컬럼은 뺐다 —
// principals 테이블에 직급 컬럼이 없고, 페르소나 선택은 화면마다 지역 상태라
// 앱 전역의 "현재 선택" 이라는 값 자체가 존재하지 않는다. 첫 행을 선택된 것처럼
// 표시하면 없는 값을 지어내는 것이 된다.
export default function PrincipalTable({ principals }: { principals: Principal[] }) {
  return (
    <Blueprint className="card" style={{ padding: 20 }}>
      <table className="table">
        <thead>
          <tr>
            <th>이름 / Name</th>
            <th>부서 / Department</th>
            <th>등급 / Clearance</th>
          </tr>
        </thead>
        <tbody>
          {principals.map((p) => (
            <tr key={p.name}>
              <td style={{ fontSize: 15 }}>{p.name}</td>
              <td>{p.department}</td>
              <td>등급 {p.clearance}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Blueprint>
  );
}
