import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { roleFor } from "@/lib/session";
import AdminSummary from "@/components/AdminSummary";
import AlertTable from "@/components/AlertTable";
import AccessTable from "@/components/AccessTable";
import InquiryDialog from "@/components/InquiryDialog";

// 사이드바가 관리자 메뉴를 숨기는 것은 프레젠테이션일 뿐이다 — 주소창에
// /admin 을 직접 입력하거나 콘솔에서 fetch('/api/access-log') 를 호출할 수
// 있으므로 서버가 역할을 다시 확인한다(레이아웃과 같은 방식,
// frontend/lib/session.ts 의 roleFor).
export default async function AdminPage() {
  const session = await auth();
  if (!session?.user?.email) {
    redirect("/");
  }
  if (roleFor(session.user.email) !== "admin") {
    // 허브(/)로 보낸다. (admin)/layout.tsx 가 같은 사용자를 보내는 곳과
    // 같아야 한다 — 어긋나면 레이아웃·페이지가 각자 다른 곳으로 튕겨
    // 착지점이 렌더 순서에 달린다. /ask 는 페르소나 쿠키 뒤에 있어 이
    // 사용자에게 없을 수도 있고, 그때는 거기서 다시 허브로 튕긴다.
    redirect("/");
  }

  return (
    <div style={{ maxWidth: 1100, display: "flex", flexDirection: "column", gap: 26 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", paddingBottom: 2 }}>
        <span className="tag tag-outline">Admin only</span>
        <span style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>
          열람 이력과 권한 이상 알림은 관리자 세션에서만 보입니다.
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
      <AdminSummary />
      <AlertTable />
      <AccessTable />
      <InquiryDialog adminEmail={session.user.email} />
    </div>
  );
}
