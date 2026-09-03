"use client";

import { useState } from "react";
import type { Principal } from "./PersonaSegment";

// W3 스펙 §3.2 가 이 고지를 "페르소나 선택기 옆" 에 두라고 했는데 선택기가
// 사라졌다. 원칙("감추면 그것이 거짓 주장이 된다")은 그대로 두고 자리만
// 여기로 옮긴다 — 상시 노출이되 작게. 배너로 크게 깔면 직원 화면이 다시
// 서비스로 안 보이고, 없애면 거짓 주장이 된다.
export default function EmployeeHeader({
  principal,
  나가기,
}: {
  principal: Principal;
  나가기: () => Promise<void>;
}) {
  const [열림, set열림] = useState(false);
  return (
    <header style={{
      background: "var(--color-surface)",
      borderBottom: "1px solid var(--color-divider)",
      padding: "18px 40px 14px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 16, fontFamily: "var(--font-heading)" }}>
            {principal.name}
            <span style={{ fontSize: 12.5, color: "var(--color-neutral-700)", fontFamily: "inherit" }}>
              {" · "}{principal.department} · 등급 {principal.clearance}
            </span>
            <button onClick={() => set열림(!열림)} className="tag tag-outline"
              style={{ marginLeft: 10, cursor: "pointer", fontSize: 11 }}>
              시연용 계정 ⓘ
            </button>
          </div>
        </div>
        <form action={나가기}>
          <button className="btn btn-secondary" type="submit">나가기 / Switch</button>
        </form>
      </div>
      {열림 && (
        <p style={{ margin: "10px 0 0", fontSize: 12.5, lineHeight: 1.7, color: "var(--color-neutral-700)", maxWidth: 720 }}>
          로그인은 실제 구글 OAuth 입니다. 부서와 등급은 시연을 위해 고른
          값이고, <strong>그 값이 실제 권한 필터를 그대로 탑니다</strong> —
          화면용 꾸밈이 아니라 SQL 의 WHERE 절이 됩니다. 실제 사내 배포라면
          이 값은 인사 시스템에서 옵니다.
        </p>
      )}
    </header>
  );
}
