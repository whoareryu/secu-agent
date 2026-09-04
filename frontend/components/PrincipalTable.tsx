"use client";

import Blueprint from "./Blueprint";
import type { Principal } from "./PersonaSegment";

// GET /api/principals 그대로. 목업에 있던 "직급" 과 "현재 선택" 컬럼은 뺐다 —
// principals 테이블에 직급 컬럼이 없고, 이 표는 "누가 무엇을 보는가" 를 나란히
// 놓는 자리이지 지금 누구로 보고 있는지를 묻는 자리가 아니다. W6 이 페르소나를
// 서버 쿠키로 올려 앱 전역의 "현재 선택" 값 자체는 생겼지만(lib/persona.ts),
// 그 값을 여기 한 행에 강조하면 이 표가 비교표에서 상태 표시기로 바뀐다.
// 지금 누구로 보는 중인지는 허브(components/Hub.tsx)와 직원 면 헤더
// (components/EmployeeHeader.tsx)가 이미 밝힌다.
export default function PrincipalTable({ principals }: { principals: Principal[] }) {
  return (
    <Blueprint className="card" style={{ padding: 20 }}>
      {/* table-scroll: 다른 세 표와 같은 이유 — 넘침을 표 안에 가둔다
          (app/_ds/industry.css). */}
      <div className="table-scroll">
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
      </div>
    </Blueprint>
  );
}
