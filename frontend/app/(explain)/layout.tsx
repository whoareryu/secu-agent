import { redirect } from "next/navigation";
import { auth, signOutAction } from "@/auth";
import { roleFor } from "@/lib/session";
import { guard, navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import Header from "@/components/Header";

// Task 3 의 직원 레이아웃과 같은 모양이되 페르소나가 없다.
export default async function ExplainLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.email) redirect("/");
  const role = roleFor(session.user.email);
  // 다른 세 면과 같이 guard 를 거친다. explain 분기는 지금 언제나 "ok" 라
  // 이 줄은 아무도 튕겨내지 않지만, 부르지 않으면 lib/surface.test.ts 의
  // "설명 면은 로그인만 되어 있으면 통과한다" 가 지키는 코드가 없어져
  // 레이아웃과 guard 가 조용히 갈릴 수 있다. hasPersona 는 여기서 판정에
  // 쓰이지 않는다 — guard 가 explain 분기에서 보지 않는다(lib/surface.ts).
  // (admin)/layout.tsx 도 같은 이유로 false 를 넘긴다.
  if (guard({ surface: "explain", hasPersona: false, role }) === "to-hub") redirect("/");
  return (
    <div className="surface-shell">
      {/* healthz: SurfaceNav.tsx 의 주석 참조 — 설명 면의 세 화면 모두
          백엔드를 부르므로 여기서만 readout 을 켠다. */}
      <SurfaceNav items={navFor("explain")} 부제="어떻게 동작하는가" healthz />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header email={session.user.email} role={role} signOutAction={signOutAction} items={navFor("explain")} />
        <div className="surface-main-pad">{children}</div>
      </main>
    </div>
  );
}
