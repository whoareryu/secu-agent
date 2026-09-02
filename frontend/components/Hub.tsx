import Blueprint from "./Blueprint";
import type { Principal } from "./PersonaSegment";

// 이 화면이 홈이다. 직원 면에서 나가면 항상 여기로 온다.
//
// 세 사람을 카드로 두는 이유: 고르는 행위 자체가 "다른 사람이면 다를 것"
// 을 예고한다. 드롭다운이면 그 예고가 사라진다.
export default function Hub({
  personas,
  선택하기,
}: {
  personas: Principal[];
  선택하기: (formData: FormData) => Promise<void>;
}) {
  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 20px 64px" }}>
      <div style={{ fontSize: 10.5, letterSpacing: ".18em", textTransform: "uppercase", color: "var(--color-accent)" }}>
        Choose an employee
      </div>
      <h1 style={{ margin: "6px 0 8px", fontSize: 30, lineHeight: 1.15 }}>어느 직원으로 둘러보시겠습니까</h1>
      <p style={{ margin: "0 0 28px", fontSize: 13.5, lineHeight: 1.7, color: "var(--color-neutral-700)" }}>
        고른 계정의 부서와 등급이 실제 권한 필터를 그대로 탑니다. 같은 질문을
        다른 계정으로 물으면 답이 달라집니다.
      </p>

      <form
        action={선택하기}
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}
      >
        {personas.map((p) => (
          <Blueprint key={p.name} as="button" className="card" name="persona" value={p.name} type="submit"
            style={{ padding: 20, textAlign: "left", cursor: "pointer", background: "var(--color-surface)" }}>
            <div style={{ fontFamily: "var(--font-heading)", fontSize: 20 }}>{p.name}</div>
            <div style={{ fontSize: 12.5, color: "var(--color-neutral-700)", marginTop: 4 }}>
              {p.department} · 등급 {p.clearance}
            </div>
          </Blueprint>
        ))}
      </form>

      <div style={{ marginTop: 40, paddingTop: 22, borderTop: "1px solid var(--color-divider)" }}>
        <a href="/how" style={{ fontSize: 13.5 }}>
          이것이 어떻게 동작하는지, 무엇을 검증했는지 보기 →
        </a>
      </div>
    </div>
  );
}
