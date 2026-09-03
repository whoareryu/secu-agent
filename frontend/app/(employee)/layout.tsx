import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { roleFor } from "@/lib/session";
import { PERSONA_COOKIE, personaFrom } from "@/lib/persona";
import { guard, navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import EmployeeHeader from "@/components/EmployeeHeader";
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

export default async function EmployeeLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.email) redirect("/");

  // 이 배포는 상시 가동이 아니다(app/page.tsx 의 같은 처리 참조) — 백엔드를
  // 켜 둔 맥이 꺼져 있으면 principals() 가 던진다. 여기서 안 잡으면 이미
  // 페르소나를 고르고 들어온 직원 화면 전체가 서버 예외를 그대로 뱉는다.
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
            꺼져 있어 직원 정보를 확인하지 못했습니다 — 켜지기 전에는
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

  const 판정 = guard({
    surface: "employee",
    hasPersona: name !== null,
    role: roleFor(session.user.email),
  });
  if (판정 === "to-hub") redirect("/");

  const principal = 목록.find((p) => p.name === name)!;

  async function 나가기() {
    "use server";
    const jar = await cookies();
    jar.delete(PERSONA_COOKIE);
    redirect("/");
  }

  return (
    <div className="surface-shell">
      <SurfaceNav items={navFor("employee")} 부제="사내 보안 규정 에이전트" />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <EmployeeHeader principal={principal} 나가기={나가기} />
        <div className="surface-main-pad">{children}</div>
      </main>
    </div>
  );
}
