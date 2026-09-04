import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { auth, signInAction, signOutAction } from "@/auth";
import { PERSONA_COOKIE, personaFrom } from "@/lib/persona";
import { guard, navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import Header from "@/components/Header";
import Blueprint from "@/components/Blueprint";
import type { Principal } from "@/components/PersonaSegment";

async function principals(): Promise<Principal[]> {
  const r = await fetch(`${process.env.BACKEND_URL}/principals`, {
    headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`principals ${r.status}`);
  return r.json();
}

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
    return (
      <div style={{ maxWidth: 900, margin: "48px auto", padding: "0 20px" }}>
        <Blueprint className="card" style={{ padding: 24, gap: 14, borderColor: "var(--color-accent-700)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="tag tag-outline">502</span>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: 22 }}>백엔드에 닿지 못했습니다</span>
          </div>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
            이 배포는 상시 가동이 아니라 필요할 때만 백엔드를 켜 둡니다. 지금
            꺼져 있어 계정 정보를 확인하지 못했습니다 — 켜지기 전에는
            새로고침해도 같은 결과입니다.
          </p>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
            <a href="/">허브로 돌아가기</a>
          </p>
        </Blueprint>
      </div>
    );
  }

  const jar = await cookies();
  const name = personaFrom(jar.get(PERSONA_COOKIE)?.value, 목록.map((p) => p.name));
  // 역할을 못 찾으면 member 로 본다 — 닫히는 방향이다.
  const role = 목록.find((p) => p.name === name)?.role ?? "member";

  // 사이드바가 관리자 메뉴를 감추는 것은 프레젠테이션일 뿐이다 — 주소창에
  // /admin 을 직접 입력할 수 있으므로 이 판정이 진짜 문이다.
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
