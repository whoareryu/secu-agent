import { redirect } from "next/navigation";
import { auth, signInAction, signOutAction } from "@/auth";
import { guard, navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import Header from "@/components/Header";

// 설명 면은 이 프로젝트가 무엇을 하는지 보여주는 곳이다. 로그인도 페르소나도
// 요구하지 않는다(스펙 §2.2) — 읽는 데 돈이 들지 않고, 문 뒤에 두면 아무도
// 읽지 않는다.
export default async function ExplainLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  // 다른 두 면과 같이 guard 를 거친다. explain 분기는 지금 언제나 "ok" 라
  // 이 줄은 아무도 튕겨내지 않지만, 부르지 않으면 lib/surface.test.ts 의
  // "설명 면은 로그인도 페르소나도 요구하지 않는다" 가 지키는 코드가 없어져
  // 레이아웃과 guard 가 조용히 갈릴 수 있다. hasPersona 도 role 도 여기서는
  // 판정에 쓰이지 않는다 — guard 가 explain 분기에서 둘 다 보지 않는다
  // (lib/surface.ts). 이 면에는 페르소나가 없으므로 역할도 없다.
  if (guard({ surface: "explain", hasPersona: false, role: "member" }) === "to-hub") redirect("/");
  return (
    <div className="surface-shell">
      {/* healthz: SurfaceNav.tsx 의 주석 참조 — 설명 면의 세 화면 모두
          백엔드를 부르므로 여기서만 readout 을 켠다. */}
      <SurfaceNav items={navFor("explain")} 부제="어떻게 동작하는가" healthz />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header
          email={session?.user?.email ?? null}
          signInAction={signInAction}
          signOutAction={signOutAction}
          items={navFor("explain")}
        />
        <div className="surface-main-pad">{children}</div>
      </main>
    </div>
  );
}
