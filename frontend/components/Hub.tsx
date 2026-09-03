import Blueprint from "./Blueprint";
import { 으로 } from "@/lib/josa";
import type { Principal } from "./PersonaSegment";

// 이 화면이 홈이다. 직원 면에서 나가면 항상 여기로 온다.
//
// 사람을 카드로 두는 이유: 고르는 행위 자체가 "다른 사람이면 다를 것"
// 을 예고한다. 드롭다운이면 그 예고가 사라진다.
//
// 아래 문구가 "같은 질문을 다른 계정으로 물으면 답이 달라집니다" 였는데
// **거짓이었다.** 계정이 10개가 된 뒤 하이브리드 검색으로 다시 실측했다
// (2026-09-03, k=10, data/principals.json 열 계정 전부, 비교 대상은
// clause_code 집합):
//   "비밀번호는 얼마나 자주 바꿔야 하나"          열 계정 전부 동일 (집합 1가지)
//   "임원 성과급은 어떤 기준으로 정해지나"         등급 3 두 명(오보안·최임원)만
//                                                6.1.x 를 받는다 (2가지)
//   "운영 서버에 접속하려면 어떤 승인이 필요한가"  개발팀 두 명(김개발·정개발)만
//                                                5.1.1 을 받는다 (2가지)
// 셋 다 components/RightRail.tsx 가 /ask 에 올려둔 샘플 질문이다. 계정이
// 셋일 때는 두 번째와 세 번째가 "한 명만 다르다" 로 같아 보여, 무엇이
// 갈랐는지가 등급인지 부서인지 구분되지 않았다 — 열 계정에서는 각각
// 등급으로, 부서로 갈린다는 것이 드러난다.
// 조건을 문장 안으로 끌어올린다 — 권한 차이가 질의에 따라 아예 보이지
// 않는다는 것이 숨길 일이 아니라 이 프로젝트가 말하려는 바다(/how 의
// 순진한 경로 패널과 같은 논지).
// 문장이 "조항" 을 말하는 이유: 위 실측이 비교한 것이 clause_code 집합이다.
// 최종 답변 문면까지 같다는 주장은 재보지 않았다.
//
// 로그아웃이 여기 있는 이유(W6 스펙 §2.6): 나가기로 직원 면을 벗어나면 허브가
// 유일하게 남는 화면인데, 여기 버튼이 없으면 로그아웃하러 설명 면까지 가야
// 했다. 스펙이 홈이라 부른 화면에 스펙의 결정이 빠져 있었다.
export default function Hub({
  personas,
  선택하기,
  email,
  signOutAction,
  활성페르소나,
}: {
  personas: Principal[];
  선택하기: (formData: FormData) => Promise<void>;
  email: string;
  signOutAction: () => Promise<void>;
  활성페르소나: string | null;
}) {
  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 20px 64px" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          paddingBottom: 22,
          marginBottom: 26,
          borderBottom: "1px solid var(--color-divider)",
        }}
      >
        <div style={{ flex: 1, minWidth: 0, lineHeight: 1.3 }}>
          <div style={{ fontSize: 13 }}>{email}</div>
          <div style={{ fontSize: 11, color: "var(--color-neutral-600)" }}>Google OAuth</div>
        </div>
        <form action={signOutAction}>
          <button className="btn btn-secondary" type="submit">
            로그아웃 / Sign out
          </button>
        </form>
      </header>

      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-accent)" }}>
        시연용 계정 고르기
      </div>
      <h1 style={{ margin: "10px 0 10px", fontSize: 36, lineHeight: 1.2 }}>어느 직원으로 둘러보시겠습니까</h1>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, margin: "0 0 28px" }}>
        <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7, color: "var(--color-neutral-700)" }}>
          고른 계정의 부서와 등급이 실제 권한 필터를 그대로 탑니다. 답이 갈리는
          것은 질문이 그 계정의 권한 밖 문서에 닿을 때입니다 — 닿지 않는 질문에서는
          열 계정이 모두 같은 근거 조항을 받습니다.
        </p>
        {활성페르소나 && (
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.7, color: "var(--color-accent-700)" }}>
            지금은 <strong>{활성페르소나}</strong>{으로(활성페르소나)} 보는 중입니다 — <a href="/ask">질의 화면</a>으로 돌아가면
            그대로 이어지고, 아래에서 다른 직원을 고르면 그 계정으로 바뀝니다.
          </p>
        )}
      </div>

      <form
        action={선택하기}
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}
      >
        {personas.map((p) => {
          // 지금 보는 중인 계정을 카드에도 표시한다. 계정이 셋일 때는 위
          // 문장 하나로 충분했지만, 열 장이 깔리면 자기 카드를 문장에서
          // 이름을 읽고 눈으로 찾아야 한다.
          const 보는중 = p.name === 활성페르소나;
          return (
            <Blueprint key={p.name} as="button" className="card" name="persona" value={p.name} type="submit"
              style={{
                padding: 20, textAlign: "left", cursor: "pointer",
                background: 보는중 ? "var(--color-accent-100)" : "var(--color-surface)",
                borderColor: 보는중 ? "var(--color-accent)" : undefined,
              }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontFamily: "var(--font-heading)", fontSize: 20 }}>{p.name}</span>
                {보는중 && <span className="tag tag-accent">보는 중</span>}
              </div>
              <div style={{ fontSize: 12.5, color: "var(--color-neutral-700)", marginTop: 4 }}>
                {p.department} · 등급 {p.clearance}
              </div>
            </Blueprint>
          );
        })}
      </form>

      <div style={{ marginTop: 40, paddingTop: 22, borderTop: "1px solid var(--color-divider)" }}>
        <a href="/how" style={{ fontSize: 13.5 }}>
          이것이 어떻게 동작하는지, 무엇을 검증했는지 보기 →
        </a>
      </div>
    </div>
  );
}
