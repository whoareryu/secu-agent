import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { auth, signInAction, signOutAction } from "@/auth";
import { PERSONA_COOKIE, personaFrom } from "@/lib/persona";
import { principals, roleOf } from "@/lib/principals";
import { guard, navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import Header from "@/components/Header";
import BackendDown from "@/components/BackendDown";
import type { Principal } from "@/components/PersonaSegment";

// 관리자 면을 여는 것은 로그인이 아니라 페르소나의 역할이다(스펙 §2.2) —
// 그래서 이 레이아웃도 직원 면처럼 페르소나를 확정해야 하고, 확정하려면
// 계정 목록을 서버에서 받아야 한다. 역할을 브라우저가 들고 오게 하면
// 그것이 곧 사칭 경로다.
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  // 이 배포는 상시 가동이 아니다(app/page.tsx 의 같은 처리 참조) — 백엔드를
  // 켜 둔 맥이 꺼져 있으면 principals() 가 던진다. 이 레이아웃이 그 호출을
  // 하게 된 이상 직원 면과 같은 카드가 여기에도 필요하다.
  let 목록: Principal[];
  try {
    목록 = await principals();
  } catch {
    return <BackendDown 무엇을="계정 정보를" />;
  }

  const jar = await cookies();
  const name = personaFrom(jar.get(PERSONA_COOKIE)?.value, 목록.map((p) => p.name));
  const role = roleOf(목록, name);

  // 이 판정이 막는 것은 **화면**이다. 데이터까지 막는다고 읽으면 안 된다 —
  // /api/log-events 와 /api/access-log 는 이제 누구나 부를 수 있다(스펙 §2.2,
  // 그 라우트들의 주석). 그쪽에서 남의 질의 원문을 가리는 것은 로그인이나
  // 역할이 아니라 백엔드의 방문자 세션 마스킹이다. 그래도 이 줄이 필요한
  // 이유는 사이드바에서 메뉴를 빼는 것이 프레젠테이션일 뿐이어서다 —
  // 주소창에 /admin 을 직접 입력하면 그 화면은 여기서만 막힌다.
  if (guard({ surface: "admin", hasPersona: name !== null, role }) === "to-hub") redirect("/");

  return (
    <div className="surface-shell">
      <SurfaceNav items={navFor("admin")} 부제="운영 · 감사" />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header
          email={session?.user?.email ?? null}
          signInAction={signInAction}
          signOutAction={signOutAction}
          items={navFor("admin")}
        />
        <div className="surface-main-pad">{children}</div>
      </main>
    </div>
  );
}
