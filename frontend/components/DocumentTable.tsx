"use client";

import Blueprint from "./Blueprint";
import type { Principal } from "./PersonaSegment";

// 정의는 lib/visibility.ts 로 옮겼다 — 서버 컴포넌트가 부를 자리가 필요했고
// (이 파일은 "use client" 라 서버에서 못 부른다), npm test 가 보는 lib/ 안에
// 있어야 테스트가 닿는다. 여기서는 기존 import 경로가 깨지지 않게 재수출만.
import { visible, type Document } from "@/lib/visibility";
export { visible, type Document };

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
      {/* table-scroll: source_path 는 슬래시로 이어진 줄바꿈 안 되는 값이라
          좁은 화면에서 표가 카드보다 넓어질 수 있다 — 표를 반응형으로 접지는
          않되(범위 밖), 그 넓어짐이 페이지 자체를 가로로 밀지 않게 여기서
          가둔다(app/_ds/industry.css). */}
      <div className="table-scroll">
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
      </div>
    </Blueprint>
  );
}
