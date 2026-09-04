"use client";

import { useState } from "react";
import Blueprint from "./Blueprint";

// 프로토타입(docs/handoff/prototype.dc.html)의 로그인 화면을 재현한다. 여기서
// 고르는 role 은 화면 전환 스위치일 뿐이다 — 실제 role 은 서버가 이메일
// 알리스트로 정한다(frontend/lib/session.ts). 그 사실을 아래 고지에 한 줄
// 더한다.
type RoleChoice = "member" | "admin";

// signInAction 은 서버 액션(frontend/auth.ts)이라 클라이언트 컴포넌트가
// 직접 import 할 수 없다 — 이 컴포넌트를 렌더하는 서버 컴포넌트가 prop 으로
// 내려준다.
export default function SignIn({ signInAction }: { signInAction: () => Promise<void> }) {
  const [roleChoice, setRoleChoice] = useState<RoleChoice>("member");

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "var(--color-bg)",
        padding: "48px 20px",
      }}
    >
      <div style={{ width: "min(420px, 100%)", display: "flex", flexDirection: "column", gap: 28 }}>
        <div>
          <div
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: 13,
              letterSpacing: ".34em",
              color: "var(--color-accent)",
              textTransform: "uppercase",
            }}
          >
            Secu-Agent
          </div>
          <h1 style={{ margin: "8px 0 0", fontSize: 38, lineHeight: 1.05, letterSpacing: "-.01em" }}>
            사내 규정 · 권한 인식 검색
            <br />
            <span style={{ color: "var(--color-neutral-600)", fontSize: 22, letterSpacing: ".02em" }}>
              Clearance-aware policy retrieval
            </span>
          </h1>
        </div>

        <Blueprint className="card" style={{ padding: 28, gap: 18 }}>
          <div className="card-kicker">Sign in</div>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: "var(--color-neutral-700)" }}>
            사내 계정으로 로그인합니다. 브라우저는 백엔드 주소도 공유 시크릿도 받지
            않으며, Next.js Route Handler 가 세션을 확인한 뒤 백엔드를 호출합니다.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            <div
              style={{
                fontSize: 11,
                letterSpacing: ".16em",
                textTransform: "uppercase",
                color: "var(--color-neutral-600)",
              }}
            >
              Role · 계정 유형
            </div>
            <div style={{ display: "flex", border: "1px solid var(--color-divider)" }}>
              <button
                type="button"
                onClick={() => setRoleChoice("member")}
                style={roleButtonStyle(roleChoice === "member")}
              >
                <span style={{ fontSize: 13.5 }}>일반 사용자</span>
                <span
                  style={{ fontSize: 10.5, letterSpacing: ".1em", textTransform: "uppercase", opacity: 0.7 }}
                >
                  Member
                </span>
              </button>
              <button
                type="button"
                onClick={() => setRoleChoice("admin")}
                style={roleButtonStyle(roleChoice === "admin")}
              >
                <span style={{ fontSize: 13.5 }}>관리자</span>
                <span
                  style={{ fontSize: 10.5, letterSpacing: ".1em", textTransform: "uppercase", opacity: 0.7 }}
                >
                  Admin
                </span>
              </button>
            </div>
            <div style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
              직원별 서류 열람 이력과 권한 밖 열람 알림은 관리자만 볼 수 있습니다.
            </div>
          </div>

          <form action={signInAction}>
            <Blueprint
              as="button"
              className="btn btn-primary"
              style={{ height: 44, fontSize: 15, letterSpacing: ".02em", width: "100%" }}
            >
              Google 계정으로 로그인 / Continue with Google
            </Blueprint>
          </form>

          <div
            style={{
              borderTop: "1px solid var(--color-divider)",
              paddingTop: 14,
              fontSize: 12.5,
              lineHeight: 1.55,
              color: "var(--color-neutral-700)",
            }}
          >
            <p style={{ margin: 0 }}>
              인증은 실제 구글 OAuth 입니다. 부서·등급은 시연을 위해 선택하는
              값이며,{" "}
              <strong style={{ color: "var(--color-accent-800)" }}>
                선택된 값이 실제 권한 필터를 그대로 탑니다.
              </strong>
            </p>
            <p style={{ margin: "6px 0 0" }}>
              관리자 여부는 이메일 알리스트로 서버가 정합니다. 여기서 고르는
              값은 화면 전환일 뿐입니다.
            </p>
          </div>
        </Blueprint>

        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "center",
            fontSize: 11,
            letterSpacing: ".14em",
            textTransform: "uppercase",
            color: "var(--color-neutral-600)",
          }}
        >
          <span>Vercel · BFF</span>
          <span style={{ flex: 1, height: 1, background: "var(--color-divider)" }} />
          <span>Cloudflare Container</span>
          <span style={{ flex: 1, height: 1, background: "var(--color-divider)" }} />
          <span>Neon · pgvector</span>
        </div>
      </div>
    </div>
  );
}

function roleButtonStyle(active: boolean): React.CSSProperties {
  return {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 1,
    padding: "10px 12px",
    background: active ? "var(--color-accent)" : "transparent",
    border: 0,
    borderRight: "1px solid var(--color-divider)",
    cursor: "pointer",
    color: active ? "var(--color-bg)" : "var(--color-text)",
    fontFamily: "var(--font-body)",
  };
}
