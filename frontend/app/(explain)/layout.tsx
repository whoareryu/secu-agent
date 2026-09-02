import { redirect } from "next/navigation";
import { auth, signOutAction } from "@/auth";
import { roleFor } from "@/lib/session";
import { navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import Header from "@/components/Header";

// Task 3 의 직원 레이아웃과 같은 모양이되 페르소나가 없다.
export default async function ExplainLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.email) redirect("/");
  // guard 를 부르지 않는다 — 설명 면은 로그인만 되어 있으면 통과이고, 그
  // 사실이 lib/surface.test.ts 의 "설명 면은 로그인만 되어 있으면 통과한다"
  // 에 있다.
  const role = roleFor(session.user.email);
  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "236px 1fr", background: "var(--color-bg)" }}>
      {/* healthz: SurfaceNav.tsx 의 주석 참조 — 설명 면의 세 화면 모두
          백엔드를 부르므로 여기서만 readout 을 켠다. */}
      <SurfaceNav items={navFor("explain")} 부제="어떻게 동작하는가" healthz />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header email={session.user.email} role={role} signOutAction={signOutAction} items={navFor("explain")} />
        <div style={{ padding: "28px 40px 56px" }}>{children}</div>
      </main>
    </div>
  );
}
