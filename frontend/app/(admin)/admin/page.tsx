import { auth } from "@/auth";
import AdminSummary from "@/components/AdminSummary";
import AlertTable from "@/components/AlertTable";
import AccessTable from "@/components/AccessTable";
import InquiryDialog from "@/components/InquiryDialog";

// 이 면을 여는 판정은 (admin)/layout.tsx 한 곳에서 한다 — 페르소나의 역할을
// guard() 에 물어본다(lib/surface.ts). 여기서 세션을 다시 보던 검사는 걷었다:
// 로그인은 더 이상 이 면의 조건이 아니고, 조건이 아닌 것을 다시 확인하면
// 판정이 두 벌이 되어 둘이 갈릴 수 있다.
//
// auth() 는 남는다. 판정에 쓰지 않고, 아래 문의 메일에 넣을 이름으로만 쓴다 —
// 로그인하지 않고 들어온 방문자면 없을 수 있다.
export default async function AdminPage() {
  const session = await auth();

  return (
    <div style={{ maxWidth: 1100, display: "flex", flexDirection: "column", gap: 26 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", paddingBottom: 2 }}>
        <span className="tag tag-outline">역할: 감사</span>
        <span style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>
          열람 이력과 권한 이상 알림은 고른 페르소나의 역할이 감사일 때만 보입니다 — 로그인은 필요하지 않습니다.
        </span>
      </div>
      <p
        style={{
          margin: 0,
          fontSize: 13,
          lineHeight: 1.6,
          color: "var(--color-accent-900)",
          background: "var(--color-accent-100)",
          padding: "12px 16px",
          border: "1px solid var(--color-accent-300)",
        }}
      >
        이 화면은 이 배포에서 실제로 일어난 요청만 보여줍니다. 표본이 적은 것은 아직 적게 썼기 때문이며, 시연용으로
        채운 데이터가 아닙니다.
      </p>
      <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
        다른 방문자의 질의 원문은 가려집니다. 이 화면이 보여주는 것은 실제로 일어난 요청이고,
        가려진 것은 그 요청의 <strong>본문뿐</strong>입니다 — 누가 · 언제 · 어떤 조항에
        닿았는지는 그대로입니다. 가리는 일은 서버가 합니다.
      </p>
      <AdminSummary />
      <AlertTable />
      <AccessTable />
      <InquiryDialog adminEmail={session?.user?.email ?? null} />
    </div>
  );
}
