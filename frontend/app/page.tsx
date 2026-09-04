import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { auth, signInAction, signOutAction } from "@/auth";
import Hub from "@/components/Hub";
import Blueprint from "@/components/Blueprint";
import { PERSONA_COOKIE, personaFrom } from "@/lib/persona";
import type { Principal } from "@/components/PersonaSegment";

// 서버 컴포넌트이므로 BFF 를 거치지 않고 백엔드를 직접 부른다. BFF 라우트가
// 있는 이유는 브라우저가 시크릿을 가질 수 없어서이고, 여기는 서버다.
async function principals(): Promise<Principal[]> {
  const r = await fetch(`${process.env.BACKEND_URL}/principals`, {
    headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`principals ${r.status}`);
  return r.json();
}

// 허브는 로그인 없이 열린다(스펙 §2.2). 예전에는 세션이 없으면 여기서
// SignIn 화면을 대신 그려 이 페이지가 곧 로그인 벽이었다 — 그 벽이 유료
// LLM 을 부르는 /ask 의 제출 하나로 좁아졌다.
export default async function Home() {
  const session = await auth();

  // 이 배포는 상시 가동이 아니다(docs/superpowers/plans/2026-09-02-w5-deploy.md
  // 결정 2) — 백엔드를 켜 둔 맥이 꺼져 있으면 principals() 가 던진다.
  // 방문자가 처음 보는 문이 서버 예외를 그대로 뱉게 둘 수 없다 —
  // app/api/ask, app/api/principals 가 이미 하는 것과 같은 모양으로 잡는다.
  let personas: Principal[];
  try {
    personas = await principals();
  } catch {
    return (
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 20px 64px" }}>
        <Blueprint className="card" style={{ padding: 24, gap: 14, borderColor: "var(--color-accent-700)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="tag tag-outline">502</span>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: 22 }}>백엔드에 닿지 못했습니다</span>
          </div>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
            이 배포는 상시 가동이 아니라 필요할 때만 백엔드를 켜 둡니다. 지금
            꺼져 있어 직원 목록을 가져오지 못했습니다 — 켜지기 전에는
            새로고침해도 같은 결과입니다.
          </p>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
            그래도 <a href="/how">이것이 어떻게 동작하는지 보기</a>의 패널
            대부분(②③④, 측정값·스키마 인용)은 백엔드 없이 그대로 열립니다 —
            라이브 시연(①)만 지금 비활성입니다.
          </p>
        </Blueprint>
      </div>
    );
  }

  async function 선택하기(formData: FormData) {
    "use server";
    const raw = String(formData.get("persona") ?? "");
    // 폼이 보낸 값을 그대로 믿지 않는다 — personaFrom 이 존재하는 이유가
    // 이것이다(lib/persona.ts). 목록에 없는 이름이면 쿠키를 심지 않고
    // 직원 면으로도 보내지 않는다.
    const name = personaFrom(raw, personas.map((p) => p.name));
    if (!name) return;
    const jar = await cookies();
    // httpOnly 로 둔다. 클라이언트 자바스크립트가 읽을 이유가 없고,
    // 읽을 수 없으면 이 값이 화면 상태로 새어나가 두 벌이 되는 일도 없다.
    //
    // secure 는 배포에서만 켠다 — 로컬 http://localhost 에서 켜면 쿠키가
    // 아예 심기지 않아 허브에서 직원 면으로 못 넘어간다.
    jar.set(PERSONA_COOKIE, name, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure: process.env.NODE_ENV === "production",
    });
    redirect("/ask");
  }

  // 허브에 서 있는데도 페르소나 쿠키가 남아 있을 수 있다 — SurfaceNav 의
  // 로고 링크가 `/` 로 오는데 그 경로는 나가기와 달리 쿠키를 지우지 않는다.
  // 그러면 사용자는 "김개발인 채로 직원 선택 화면" 에 서 있게 된다. 그 상태를
  // 숨기지 않고 화면이 밝힌다(아래 Hub 의 활성페르소나). 지우는 쪽이 아니라
  // 밝히는 쪽을 고른 이유: 로고를 눌러 돌아온 사람이 /ask 로 되돌아가면
  // 여전히 그 계정이고, 링크가 조용히 쿠키를 지우면 그 사실이 어긋난다.
  const jar = await cookies();
  const 활성페르소나 = personaFrom(jar.get(PERSONA_COOKIE)?.value, personas.map((p) => p.name));

  return (
    <Hub
      personas={personas}
      선택하기={선택하기}
      email={session?.user?.email ?? null}
      signInAction={signInAction}
      signOutAction={signOutAction}
      활성페르소나={활성페르소나}
    />
  );
}
