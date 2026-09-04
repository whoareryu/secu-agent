import Blueprint from "./Blueprint";

// 직원 셸과 관리자 셸이 백엔드에 닿지 못했을 때 그리는 카드. 두 레이아웃이
// 같은 카드를 한 단어(직원 정보 / 계정 정보)만 다르게 들고 있었다.
//
// 그 한 단어를 없애지 않고 prop 으로 받는다 — 두 면이 못 가져온 것은 실제로
// 다르고, 문구를 합쳐 "정보를 확인하지 못했습니다" 로 뭉개면 어느 쪽이
// 비어서 이 카드가 떴는지 화면이 말하지 못하게 된다.
export default function BackendDown({ 무엇을 }: { 무엇을: string }) {
  return (
    <div style={{ maxWidth: 900, margin: "48px auto", padding: "0 20px" }}>
      <Blueprint className="card" style={{ padding: 24, gap: 14, borderColor: "var(--color-accent-700)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="tag tag-outline">502</span>
          <span style={{ fontFamily: "var(--font-heading)", fontSize: 22 }}>백엔드에 닿지 못했습니다</span>
        </div>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          이 배포는 상시 가동이 아니라 필요할 때만 백엔드를 켜 둡니다. 지금
          꺼져 있어 {무엇을} 확인하지 못했습니다 — 켜지기 전에는
          새로고침해도 같은 결과입니다.
        </p>
        <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          <a href="/">허브로 돌아가기</a>
        </p>
      </Blueprint>
    </div>
  );
}
