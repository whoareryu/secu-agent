# W6 구현 계획 — 페르소나를 세션 정체성으로

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 방문자가 세 직원 중 하나를 골라 **그 사람이 되어** 서비스를 쓰고,
나가면 다시 고를 수 있게 한다. 설명·검증 화면과 관리자 화면은 별도 면으로
분리한다.

**Architecture:** 페르소나를 서버 쿠키(**이름만**)로 올려 서버 셸이 읽는다.
Next.js 라우트 그룹으로 면을 넷으로 나누고(허브·직원·설명·관리자), 면별
접근 판정과 네비 구성을 `lib/` 의 순수 함수로 빼 테스트한다. 감사 로그는
`log_events` 를 **주체의 눈으로** 보여준다 — 권한 없는 조회 경로를 만들지
않는다.

**Tech Stack:** Next.js 16(App Router, 서버 컴포넌트·서버 액션), Auth.js,
FastAPI, psycopg 3, node:test

**Spec:** `docs/superpowers/specs/2026-09-02-persona-as-session-design.md`
**상위 Spec:** `docs/superpowers/specs/2026-08-31-secu-agent-design.md`

## Global Constraints

- 커밋 메시지는 한국어, 평서형 과거 (`~했다`).
- **쿠키에 담기는 것은 페르소나 이름뿐이다.** 등급·부서를 담지 않는다 —
  `api/schemas.py` 가 적어둔 사칭 경로 원칙이 쿠키에도 그대로 적용된다.
- **권한 필터를 우회하는 조회 경로를 만들지 않는다.** `LogSearch.query()` 는
  `Principal` 을 필수로 받는다. 관리자 편의를 위해서도 예외를 만들지 않는다.
- 하드코딩된 색 금지 — `app/_ds/industry.css` 의 `var(--color-…)`.
- `.blueprint` 를 쓰는 모든 요소는 `components/Blueprint.tsx` 를 거친다.
- `NEXT_PUBLIC_` 금지 — 백엔드 주소·시크릿은 서버에서만 읽는다.
- 화면에 뒷받침 없는 문장을 한 줄도 두지 않는다.
- **Next.js 16 에서 `cookies()` 는 비동기다** — `const jar = await cookies()`.

## File Structure

| 파일 | 책임 |
|---|---|
| `frontend/lib/persona.ts` (신규) | 쿠키 이름 상수, 쿠키값 → 유효한 페르소나 이름 판정 |
| `frontend/lib/persona.test.ts` (신규) | 위의 테스트 |
| `frontend/lib/surface.ts` (신규) | 면 정의, 면별 네비, 면 접근 판정 |
| `frontend/lib/surface.test.ts` (신규) | 위의 테스트 |
| `frontend/app/page.tsx` (수정) | 미로그인 → 로그인, 로그인 → **허브** |
| `frontend/components/Hub.tsx` (신규) | 직원 카드 + 설명 면 입구. 반응형 |
| `frontend/app/(employee)/layout.tsx` (신규) | 직원 면 셸 — 쿠키 확인, 헤더에 정체성 |
| `frontend/components/EmployeeHeader.tsx` (신규) | 정체성 + 시연 고지 + 나가기 |
| `frontend/app/(employee)/ask/page.tsx` (이동·수정) | 선택기 없는 질의 화면 |
| `frontend/app/(employee)/my/documents/page.tsx` (신규) | 내가 볼 수 있는 문서 |
| `frontend/app/(explain)/layout.tsx` (신규) | 설명 면 셸 |
| `frontend/app/(explain)/{documents,principals,how}/page.tsx` (이동) | 설명 화면들 |
| `frontend/app/(admin)/layout.tsx` (신규) | 관리자 면 셸 — role 재확인 |
| `frontend/app/(admin)/{admin,logs}/page.tsx` (이동·신규) | 관리자 화면들 |
| `frontend/app/api/log-events/route.ts` (신규) | BFF. 관리자 확인 후 중계 |
| `backend/api/main.py` (수정) | `GET /log-events` |
| `backend/api/schemas.py` (수정) | `LogEventView` |
| `backend/tests/test_api_log_events.py` (신규) | 새 엔드포인트 |

---

## Task 1: 판정 로직을 순수 함수로

**Files:**
- Create: `frontend/lib/persona.ts`, `frontend/lib/persona.test.ts`
- Create: `frontend/lib/surface.ts`, `frontend/lib/surface.test.ts`

**Interfaces:**
- Produces: `PERSONA_COOKIE: string`, `personaFrom(raw: string | undefined, known: string[]): string | null`
- Produces: `type Surface = "employee" | "explain" | "admin"`,
  `navFor(surface: Surface): NavItem[]`,
  `guard(input: {surface: Surface; hasPersona: boolean; role: Role}): "ok" | "to-hub" | "to-login"`

- [ ] **Step 1: `persona.ts` 의 실패하는 테스트를 쓴다**

`frontend/lib/persona.test.ts`:

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { personaFrom } from "./persona.ts";

// 쿠키는 브라우저가 보내는 값이라 믿지 않는다. 여기서 걸러지지 않으면
// 알 수 없는 이름이 그대로 백엔드로 가고, 백엔드는 "알 수 없는 페르소나"
// 400 을 내며 화면은 원인을 말하지 못한 채 깨진다.

const 세명 = ["김개발", "박인사", "최임원"];

test("알려진 이름은 그대로 통과한다", () => {
  assert.equal(personaFrom("김개발", 세명), "김개발");
  assert.equal(personaFrom("최임원", 세명), "최임원");
});

test("알려지지 않은 이름은 null", () => {
  assert.equal(personaFrom("없는사람", 세명), null);
});

test("쿠키가 없으면 null", () => {
  assert.equal(personaFrom(undefined, 세명), null);
  assert.equal(personaFrom("", 세명), null);
});

test("목록이 비어 있으면 무엇도 통과하지 않는다", () => {
  // 백엔드가 죽어 principals 를 못 불러왔을 때 이 함수가 열리는 쪽으로
  // 틀리면, 아무 이름이나 담긴 쿠키로 직원 면에 들어간다.
  assert.equal(personaFrom("김개발", []), null);
});

test("앞뒤 공백이 붙은 값은 통과하지 않는다", () => {
  // 공백을 잘라 받아주면 " 김개발 " 과 "김개발" 이 다른 쿠키인데 같은
  // 사람이 되어, 나중에 쿠키를 키로 쓰는 코드가 조용히 갈린다.
  assert.equal(personaFrom(" 김개발", 세명), null);
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd frontend && npm test`
Expected: FAIL — `Cannot find module './persona.ts'`

- [ ] **Step 3: `persona.ts` 를 쓴다**

```ts
// 페르소나 이름을 담는 쿠키. **이름만 담는다** — 등급·부서를 담으면
// 클라이언트가 자기 권한을 정하게 되고, 그것이 api/schemas.py 가 막아둔
// 사칭 경로다. 이름은 백엔드가 principals 테이블에서 등급으로 번역한다.
export const PERSONA_COOKIE = "secuagent_persona";

// 쿠키값이 실제로 존재하는 페르소나인지 판정한다. 목록은 호출부가
// 백엔드에서 받아 넘긴다 — 이름을 여기에 하드코딩하면 계정이 늘었을 때
// 화면이 따라오지 못한다.
export function personaFrom(raw: string | undefined, known: string[]): string | null {
  if (!raw) return null;
  return known.includes(raw) ? raw : null;
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd frontend && npm test`
Expected: PASS 5건

- [ ] **Step 5: `surface.ts` 의 실패하는 테스트를 쓴다**

`frontend/lib/surface.test.ts`:

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { guard, navFor } from "./surface.ts";

// 면 접근 판정은 컴포넌트 안에 두지 않는다. 지금 프론트엔드에는 컴포넌트를
// 도는 자동 검증이 하나도 없어서(npm test 는 lib/ 만 본다), 컴포넌트 안에
// 넣는 순간 이 판정은 아무도 검사하지 않는 코드가 된다.

test("직원 면은 페르소나가 없으면 허브로 보낸다", () => {
  assert.equal(guard({ surface: "employee", hasPersona: false, role: "member" }), "to-hub");
});

test("직원 면은 페르소나가 있으면 통과한다", () => {
  assert.equal(guard({ surface: "employee", hasPersona: true, role: "member" }), "ok");
});

test("관리자 면은 member 를 허브로 보낸다", () => {
  // 사이드바에서 메뉴를 빼는 것은 프레젠테이션일 뿐이다 — 주소창에 직접
  // 입력할 수 있으므로 이 판정이 진짜 문이다.
  assert.equal(guard({ surface: "admin", hasPersona: false, role: "member" }), "to-hub");
  assert.equal(guard({ surface: "admin", hasPersona: true, role: "member" }), "to-hub");
});

test("관리자 면은 admin 을 페르소나 없이도 통과시킨다", () => {
  // 관리자 면은 한 사람이 되어보는 곳이 아니라 장치를 들여다보는 곳이다.
  assert.equal(guard({ surface: "admin", hasPersona: false, role: "admin" }), "ok");
});

test("설명 면은 로그인만 되어 있으면 통과한다", () => {
  assert.equal(guard({ surface: "explain", hasPersona: false, role: "member" }), "ok");
});

test("직원 면 네비에 설명·관리자 항목이 없다", () => {
  // 직원 화면에 "직원이 볼 리 없는 메뉴" 가 섞이면 그 화면은 다시
  // 조작판으로 읽힌다.
  const ids = navFor("employee").map((i) => i.id);
  assert.deepEqual(ids, ["ask", "my-docs"]);
});

test("관리자 면 네비에 감사 로그가 있다", () => {
  assert.deepEqual(navFor("admin").map((i) => i.id), ["logs", "admin"]);
});
```

- [ ] **Step 6: 실패를 확인한다**

Run: `cd frontend && npm test`
Expected: FAIL — `Cannot find module './surface.ts'`

- [ ] **Step 7: `surface.ts` 를 쓴다**

```ts
import type { Role } from "./session.ts";
import type { NavItem } from "./types.ts";

// 화면을 네 면으로 나눈다. 허브는 면이 아니라 그 셋으로 들어가는 입구라
// 여기 없다.
export type Surface = "employee" | "explain" | "admin";

const NAV: Record<Surface, NavItem[]> = {
  employee: [
    { id: "ask", ko: "질의", en: "Ask", badge: "", href: "/ask", adminOnly: false },
    { id: "my-docs", ko: "내 문서", en: "My documents", badge: "", href: "/my/documents", adminOnly: false },
  ],
  explain: [
    { id: "how", ko: "동작 원리", en: "How it works", badge: "", href: "/how", adminOnly: false },
    { id: "docs", ko: "문서 가시성", en: "Visibility", badge: "", href: "/documents", adminOnly: false },
    { id: "principals", ko: "계정", en: "Principals", badge: "", href: "/principals", adminOnly: false },
  ],
  admin: [
    { id: "logs", ko: "감사 로그", en: "Audit log", badge: "ADMIN", href: "/logs", adminOnly: true },
    { id: "admin", ko: "관리자 대시보드", en: "Admin", badge: "ADMIN", href: "/admin", adminOnly: true },
  ],
};

export function navFor(surface: Surface): NavItem[] {
  return NAV[surface];
}

// 면에 들어갈 수 있는지 판정한다. 세션 확인은 각 레이아웃이 이미 하므로
// 여기서는 세션이 있다고 본다 — "to-login" 은 그 판정이 이 함수로 옮겨올
// 날을 위해 남겨둔 값이 아니라, 호출부가 세션 없음을 알았을 때 쓰는 값이다.
export function guard(input: {
  surface: Surface;
  hasPersona: boolean;
  role: Role;
}): "ok" | "to-hub" | "to-login" {
  if (input.surface === "admin" && input.role !== "admin") return "to-hub";
  if (input.surface === "employee" && !input.hasPersona) return "to-hub";
  return "ok";
}
```

- [ ] **Step 8: 통과를 확인한다**

Run: `cd frontend && npm test`
Expected: PASS 12건 (기존 11 + 새 7 = 18건 중 이 파일 7건)

- [ ] **Step 9: 변이로 무는지 확인한다**

`guard` 의 admin 검사를 지우고 `npm test` 를 돌려 "관리자 면은 member 를
허브로 보낸다" 가 실패하는 것을 확인한 뒤 되돌린다. 출력을 보고서에 적는다.

- [ ] **Step 10: 커밋**

```bash
cd frontend && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit && npm test
cd .. && git add frontend/lib/persona.ts frontend/lib/persona.test.ts \
  frontend/lib/surface.ts frontend/lib/surface.test.ts
git commit -m "면 접근 판정과 페르소나 해석을 순수 함수로 뺐다"
```

---

## Task 2: 허브 화면

**Files:**
- Create: `frontend/components/Hub.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: `PERSONA_COOKIE` (Task 1)
- Produces: 서버 액션 `선택하기(formData: FormData)` — 쿠키를 심고 `/ask` 로 보낸다

- [ ] **Step 1: 허브를 만든다**

`frontend/components/Hub.tsx`. 서버 컴포넌트다 — 상태가 없다.

```tsx
import Blueprint from "./Blueprint";
import type { Principal } from "./PersonaSegment";

// 이 화면이 홈이다. 직원 면에서 나가면 항상 여기로 온다.
//
// 세 사람을 카드로 두는 이유: 고르는 행위 자체가 "다른 사람이면 다를 것"
// 을 예고한다. 드롭다운이면 그 예고가 사라진다.
export default function Hub({
  personas,
  선택하기,
}: {
  personas: Principal[];
  선택하기: (formData: FormData) => Promise<void>;
}) {
  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 20px 64px" }}>
      <div style={{ fontSize: 10.5, letterSpacing: ".18em", textTransform: "uppercase", color: "var(--color-accent)" }}>
        Choose an employee
      </div>
      <h1 style={{ margin: "6px 0 8px", fontSize: 30, lineHeight: 1.15 }}>어느 직원으로 둘러보시겠습니까</h1>
      <p style={{ margin: "0 0 28px", fontSize: 13.5, lineHeight: 1.7, color: "var(--color-neutral-700)" }}>
        고른 계정의 부서와 등급이 실제 권한 필터를 그대로 탑니다. 같은 질문을
        다른 계정으로 물으면 답이 달라집니다.
      </p>

      <form
        action={선택하기}
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}
      >
        {personas.map((p) => (
          <Blueprint key={p.name} as="button" className="card" name="persona" value={p.name} type="submit"
            style={{ padding: 20, textAlign: "left", cursor: "pointer", background: "var(--color-surface)" }}>
            <div style={{ fontFamily: "var(--font-heading)", fontSize: 20 }}>{p.name}</div>
            <div style={{ fontSize: 12.5, color: "var(--color-neutral-700)", marginTop: 4 }}>
              {p.department} · 등급 {p.clearance}
            </div>
          </Blueprint>
        ))}
      </form>

      <div style={{ marginTop: 40, paddingTop: 22, borderTop: "1px solid var(--color-divider)" }}>
        <a href="/how" style={{ fontSize: 13.5 }}>
          이것이 어떻게 동작하는지, 무엇을 검증했는지 보기 →
        </a>
      </div>
    </div>
  );
}
```

`minmax(240px, 1fr)` 의 `auto-fit` 이 좁은 화면에서 카드를 세로로 쌓는다 —
스펙 §6 이 허브만 반응형에 넣은 이유가 이 한 줄이다.

- [ ] **Step 2: `app/page.tsx` 가 허브를 그리게 한다**

```tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { auth, signInAction } from "@/auth";
import SignIn from "@/components/SignIn";
import Hub from "@/components/Hub";
import { PERSONA_COOKIE } from "@/lib/persona";
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

export default async function Home() {
  const session = await auth();
  if (!session?.user?.email) {
    return <SignIn signInAction={signInAction} />;
  }

  async function 선택하기(formData: FormData) {
    "use server";
    const name = String(formData.get("persona") ?? "");
    const jar = await cookies();
    // httpOnly 로 둔다. 클라이언트 자바스크립트가 읽을 이유가 없고,
    // 읽을 수 없으면 이 값이 화면 상태로 새어나가 두 벌이 되는 일도 없다.
    jar.set(PERSONA_COOKIE, name, { httpOnly: true, sameSite: "lax", path: "/" });
    redirect("/ask");
  }

  return <Hub personas={await principals()} 선택하기={선택하기} />;
}
```

- [ ] **Step 3: 브라우저에서 확인한다**

`npm run dev` → `http://localhost:3000` 로그인 후:
- 세 카드가 보인다
- 창을 좁히면 카드가 세로로 쌓인다
- 카드를 누르면 `/ask` 로 간다 (아직 셸은 예전 것이다 — 정상)

- [ ] **Step 4: 게이트와 커밋**

```bash
cd frontend && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit && npm test && npm run build
cd .. && git add frontend/components/Hub.tsx frontend/app/page.tsx
git commit -m "직원을 고르는 허브 화면을 더했다"
```

---

## Task 3: 직원 면 셸

**Files:**
- Create: `frontend/app/(employee)/layout.tsx`, `frontend/components/EmployeeHeader.tsx`
- Create: `frontend/components/SurfaceNav.tsx`

**Interfaces:**
- Consumes: `personaFrom`, `PERSONA_COOKIE`, `guard`, `navFor` (Task 1)
- Produces: 서버 액션 `나가기()` — 쿠키를 지우고 `/` 로

- [ ] **Step 1: 면 공용 네비를 만든다**

`frontend/components/SurfaceNav.tsx` — 기존 `Sidebar.tsx` 의 모양을 그대로
쓰되 항목을 prop 으로 받는다. 기존 `Sidebar.tsx` 는 Task 6·7 이 마지막
사용처를 옮긴 뒤 지운다.

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { NavItem } from "@/lib/types";

export default function SurfaceNav({ items, 부제 }: { items: NavItem[]; 부제: string }) {
  const pathname = usePathname();
  return (
    <aside style={{ background: "var(--color-accent-900)", color: "var(--color-on-accent)",
      display: "flex", flexDirection: "column", padding: "24px 0" }}>
      <div style={{ padding: "0 20px 22px" }}>
        <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
          <div style={{ fontFamily: "var(--font-heading)", fontSize: 19, letterSpacing: ".28em", textTransform: "uppercase" }}>
            Secu-Agent
          </div>
        </Link>
        <div style={{ fontSize: 11, letterSpacing: ".1em", color: "var(--color-on-accent-faint)", marginTop: 2 }}>
          {부제}
        </div>
      </div>
      <nav style={{ display: "flex", flexDirection: "column" }}>
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link key={item.id} href={item.href}
              style={{ padding: "11px 20px", color: "inherit", textDecoration: "none",
                background: active ? "var(--color-accent-800)" : "transparent",
                display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                <span style={{ fontSize: 14 }}>{item.ko}</span>
                <span style={{ fontSize: 10.5, letterSpacing: ".12em", textTransform: "uppercase", opacity: 0.55 }}>
                  {item.en}
                </span>
              </span>
              <span style={{ fontSize: 10, opacity: 0.5 }}>{item.badge}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: 직원 헤더를 만든다**

`frontend/components/EmployeeHeader.tsx`. **스펙 §2.3 의 고지가 사는 집이다.**

```tsx
"use client";

import { useState } from "react";
import type { Principal } from "./PersonaSegment";

// W3 스펙 §3.2 가 이 고지를 "페르소나 선택기 옆" 에 두라고 했는데 선택기가
// 사라졌다. 원칙("감추면 그것이 거짓 주장이 된다")은 그대로 두고 자리만
// 여기로 옮긴다 — 상시 노출이되 작게. 배너로 크게 깔면 직원 화면이 다시
// 서비스로 안 보이고, 없애면 거짓 주장이 된다.
export default function EmployeeHeader({
  principal,
  나가기,
}: {
  principal: Principal;
  나가기: () => Promise<void>;
}) {
  const [열림, set열림] = useState(false);
  return (
    <header style={{ borderBottom: "1px solid var(--color-divider)", padding: "18px 40px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 16, fontFamily: "var(--font-heading)" }}>
            {principal.name}
            <span style={{ fontSize: 12.5, color: "var(--color-neutral-700)", fontFamily: "inherit" }}>
              {" · "}{principal.department} · 등급 {principal.clearance}
            </span>
            <button onClick={() => set열림(!열림)} className="tag tag-outline"
              style={{ marginLeft: 10, cursor: "pointer", fontSize: 11 }}>
              시연용 계정 ⓘ
            </button>
          </div>
        </div>
        <form action={나가기}>
          <button className="btn btn-secondary" type="submit">나가기 / Switch</button>
        </form>
      </div>
      {열림 && (
        <p style={{ margin: "10px 0 0", fontSize: 12.5, lineHeight: 1.7, color: "var(--color-neutral-700)", maxWidth: 720 }}>
          로그인은 실제 구글 OAuth 입니다. 부서와 등급은 시연을 위해 고른
          값이고, <strong>그 값이 실제 권한 필터를 그대로 탑니다</strong> —
          화면용 꾸밈이 아니라 SQL 의 WHERE 절이 됩니다. 실제 사내 배포라면
          이 값은 인사 시스템에서 옵니다.
        </p>
      )}
    </header>
  );
}
```

- [ ] **Step 3: 직원 면 레이아웃을 만든다**

`frontend/app/(employee)/layout.tsx`:

```tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { roleFor } from "@/lib/session";
import { PERSONA_COOKIE, personaFrom } from "@/lib/persona";
import { guard, navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import EmployeeHeader from "@/components/EmployeeHeader";
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

  const 목록 = await principals();
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
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "236px 1fr", background: "var(--color-bg)" }}>
      <SurfaceNav items={navFor("employee")} 부제="사내 보안 규정 에이전트" />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <EmployeeHeader principal={principal} 나가기={나가기} />
        <div style={{ padding: "28px 40px 56px" }}>{children}</div>
      </main>
    </div>
  );
}
```

- [ ] **Step 4: 게이트와 커밋**

```bash
cd frontend && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit && npm test && npm run build
cd .. && git add frontend/app/\(employee\)/layout.tsx \
  frontend/components/EmployeeHeader.tsx frontend/components/SurfaceNav.tsx
git commit -m "직원 면 셸과 시연 고지를 헤더에 두었다"
```

---

## Task 4: 질의 화면을 직원 면으로 옮기고 선택기를 걷어낸다

**Files:**
- Move: `frontend/app/(app)/ask/page.tsx` → `frontend/app/(employee)/ask/page.tsx`
- Modify: `frontend/components/AskPanel.tsx`
- Modify: `frontend/app/api/ask/route.ts`

**Interfaces:**
- Consumes: 직원 면 레이아웃(Task 3)이 페르소나를 보증한다
- Produces: `POST /api/ask` 가 본문의 `persona` 대신 **쿠키**에서 이름을 읽는다

- [ ] **Step 1: BFF 가 쿠키에서 페르소나를 읽게 한다**

`frontend/app/api/ask/route.ts` 에서 본문의 `persona` 를 없앤다:

```ts
import { cookies } from "next/headers";
import { PERSONA_COOKIE } from "@/lib/persona";
// … 기존 import 유지

  let query;
  try {
    ({ query } = await req.json());
  } catch {
    return Response.json({ error: "잘못된 요청 본문입니다" }, { status: 400 });
  }

  // 페르소나는 본문이 아니라 쿠키에서 읽는다. 본문으로 받으면 화면이
  // 보여주는 사람과 질의하는 사람이 갈릴 수 있다 — 헤더에는 김개발이
  // 떠 있는데 최임원으로 묻는 요청을 만들 수 있게 된다.
  const jar = await cookies();
  const persona = jar.get(PERSONA_COOKIE)?.value;
  if (!persona) {
    return Response.json({ error: "직원을 먼저 선택해 주세요" }, { status: 400 });
  }
```

`body: JSON.stringify({ query, persona })` 는 그대로 둔다 — 백엔드 계약은
바뀌지 않는다.

- [ ] **Step 2: `AskPanel` 에서 선택기를 걷어낸다**

`PersonaSegment` import 와 `personas`·`personasError`·`persona`·
`onPersonaChange` prop 을 지운다. 요청 본문에서도 `persona` 를 뺀다:

```ts
body: JSON.stringify({ query }),
```

- [ ] **Step 3: `RightRail` 의 "세 계정 비교" 를 걷어낸다**

`components/RightRail.tsx` 에는 지금 **"같은 질문 · 세 계정"** 카드가 있고,
`compare()` 가 `/api/ask` 를 `body: {query, persona: p.name}` 로 세 번
호출한다. 이것을 지운다. `personas` prop 과 `CompareRow` 타입, `comparing`·
`results` 상태, `AskResult` import 도 함께 사라진다. **남기는 것은 샘플 질의
카드뿐이다.**

지우는 이유 셋:

1. **구조적으로 깨진다.** Step 1 이 `/api/ask` 를 쿠키에서 읽게 바꾼다.
   본문의 `persona` 는 무시되므로 이 버튼은 같은 사람에게 세 번 묻게 된다.
   본문 경로를 되살리면 헤더에는 김개발이 떠 있는데 최임원으로 묻는 요청을
   만들 수 있게 되고, 그것이 이 설계가 없애려는 바로 그 어긋남이다.
2. **더 나은 같은 것이 이미 있다.** `/how` 의 패널 ① 이 같은 비교를
   라이브로 하고, LLM 을 부르지 않아 **요금이 0원**이다. 이쪽은 질의 3회를
   쓴다(카드가 그렇게 적어두고 있다).
3. **직원 화면에 있을 내용이 아니다.** 직원은 자기 화면에서 남의 결과를
   보지 않는다. 그것이 이 계획이 면을 나눈 이유다.

- [ ] **Step 4: 질의 화면을 옮기고 줄인다**

`frontend/app/(employee)/ask/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import AskPanel from "@/components/AskPanel";
import RightRail from "@/components/RightRail";

// 페르소나는 이 화면이 모른다 — 셸이 쿠키로 정하고 BFF 가 쿠키에서 읽는다.
export default function AskPage() {
  const [query, setQuery] = useState("");
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 320px", gap: 32,
      alignItems: "start", maxWidth: 1240 }}>
      <AskPanel query={query} onQueryChange={setQuery} />
      <RightRail query={query} onSelectSample={setQuery} />
    </div>
  );
}
```

`RightRail` 은 `personas` 를 더 받지 않으므로 `query` 와 `onSelectSample`
둘만 남는다.

- [ ] **Step 5: 비교 기능이 갈 곳을 화면이 밝힌다**

`RightRail` 의 샘플 카드 아래에 한 줄을 둔다 — 지운 기능을 찾는 사람이
길을 잃지 않게, 그리고 그것이 **더 싼 곳**에 있다는 사실까지 적는다.

```tsx
<p style={{ margin: 0, fontSize: 11.5, color: "var(--color-neutral-600)" }}>
  같은 질문을 세 계정으로 비교하는 것은{" "}
  <a href="/how">동작 원리</a> 화면에서 볼 수 있습니다 — 그쪽은 LLM 을 부르지
  않아 질의 횟수를 쓰지 않습니다.
</p>
```

- [ ] **Step 6: 브라우저에서 확인한다**

허브에서 김개발 → 질의 → 답변. 헤더에 김개발이 뜨고 화면에 선택기가 없다.
나가기 → 허브 → 최임원 → 같은 질문에 다른 답.

- [ ] **Step 7: 게이트와 커밋**

```bash
cd frontend && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit && npm test && npm run build
cd .. && git add frontend/app frontend/components/AskPanel.tsx frontend/components/RightRail.tsx
git commit -m "질의 화면에서 페르소나 선택기와 세 계정 비교를 걷어냈다"
```

---

## Task 5: 내 문서

**Files:**
- Create: `frontend/app/(employee)/my/documents/page.tsx`

**Interfaces:**
- Consumes: `visible()` (`components/DocumentTable.tsx`), 셸이 보증한 페르소나

- [ ] **Step 1: 화면을 만든다**

서버 컴포넌트다. 문서 목록과 페르소나를 서버에서 받아 **거른 뒤** 그린다.

```tsx
import { cookies } from "next/headers";
import Blueprint from "@/components/Blueprint";
import { visible, type Document } from "@/components/DocumentTable";
import { PERSONA_COOKIE } from "@/lib/persona";
import type { Principal } from "@/components/PersonaSegment";

async function 백엔드<T>(path: string): Promise<T> {
  const r = await fetch(`${process.env.BACKEND_URL}${path}`, {
    headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

// GET /documents 는 권한 필터 없이 전부 돌려준다(그 엔드포인트의 독스트링
// 참고 — 검색 경로가 아니라 카탈로그다). 이 화면은 **서버에서** 걸러 그린다.
// 클라이언트로 전부 내려보내고 화면에서 숨기면, 못 보는 문서의 제목이
// 브라우저에 도착한다 — 제목만으로 존재가 드러난다는 것이 이 프로젝트가
// access_records 에서 제목을 뺀 이유다.
export default async function MyDocumentsPage() {
  const jar = await cookies();
  const name = jar.get(PERSONA_COOKIE)?.value;
  const [문서, 계정] = await Promise.all([
    백엔드<Document[]>("/documents"),
    백엔드<Principal[]>("/principals"),
  ]);
  const me = 계정.find((p) => p.name === name)!;
  const 보이는것 = 문서.filter((d) => visible(d, me));

  return (
    <div style={{ maxWidth: 1000, display: "flex", flexDirection: "column", gap: 18 }}>
      <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7, color: "var(--color-neutral-700)" }}>
        {me.department} · 등급 {me.clearance} 로 열람 가능한 문서 {보이는것.length}건입니다.
        다른 계정으로 들어오면 이 목록의 길이가 달라집니다.
      </p>
      {보이는것.map((d) => (
        <Blueprint key={d.id} className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 15, fontFamily: "var(--font-heading)" }}>{d.title}</div>
          <div style={{ fontSize: 12, color: "var(--color-neutral-700)", marginTop: 4 }}>
            {d.doc_type} · 조각 {d.chunk_count}개 · 요구 등급 {d.required_clearance}
            {d.allowed_departments.length > 0 && ` · ${d.allowed_departments.join(", ")} 전용`}
          </div>
        </Blueprint>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 세 계정으로 목록 길이가 다른지 확인한다**

브라우저에서 김개발 → 내 문서 → 건수를 적는다. 나가기 → 최임원 → 다시
적는다. **두 수가 같으면 이 화면은 아무것도 증명하지 못한다** — 그때는
코퍼스 배치를 확인한다.

- [ ] **Step 3: 게이트와 커밋**

```bash
cd frontend && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit && npm test && npm run build
cd .. && git add frontend/app/\(employee\)/my
git commit -m "내가 볼 수 있는 문서 화면을 더했다"
```

---

## Task 6: 설명 면

**Files:**
- Create: `frontend/app/(explain)/layout.tsx`
- Move: `how`, `documents`, `principals` 를 `(app)` 에서 `(explain)` 로
- Modify: `frontend/app/(explain)/documents/page.tsx` (가시성 표만 남긴다)

- [ ] **Step 1: 설명 면 레이아웃을 만든다**

Task 3 의 직원 레이아웃과 같은 모양이되 페르소나가 없다.

```tsx
import { redirect } from "next/navigation";
import { auth, signOutAction } from "@/auth";
import { roleFor } from "@/lib/session";
import { navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import Header from "@/components/Header";

export default async function ExplainLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.email) redirect("/");
  // guard 를 부르지 않는다 — 설명 면은 로그인만으로 통과이고, 그 사실이
  // surface.test.ts 의 "설명 면은 로그인만 되어 있으면 통과한다" 에 있다.
  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "236px 1fr", background: "var(--color-bg)" }}>
      <SurfaceNav items={navFor("explain")} 부제="어떻게 동작하는가" />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header email={session.user.email} role={roleFor(session.user.email)} signOutAction={signOutAction} />
        <div style={{ padding: "28px 40px 56px" }}>{children}</div>
      </main>
    </div>
  );
}
```

`components/Header.tsx` 는 지금 `NAV_ITEMS` 를 직접 import 해 현재 경로로
제목을 찾는다. `NAV_ITEMS` 는 Task 7 에서 사라지므로 **항목 배열을 prop 으로
받도록 고친다** — `items: NavItem[]` 을 더하고 `NAV_ITEMS` import 를 지운다.
설명 면은 `navFor("explain")`, 관리자 면은 `navFor("admin")` 을 넘긴다.

- [ ] **Step 2: 세 화면을 옮긴다**

```bash
git mv "frontend/app/(app)/how" "frontend/app/(explain)/how"
git mv "frontend/app/(app)/documents" "frontend/app/(explain)/documents"
git mv "frontend/app/(app)/principals" "frontend/app/(explain)/principals"
```

- [ ] **Step 3: 문서 화면을 가시성 표로 줄인다**

`(explain)/documents/page.tsx` 는 이미 페르소나별 가시성을 계산해 보여준다.
제목과 설명만 그 역할에 맞게 고친다 — "문서 · 권한" → "문서 가시성". 이
화면의 페르소나 선택기는 **남긴다**: 여기는 "누가 무엇을 보는가" 를 비교하는
자리라 주체를 바꿔보는 것이 이 화면의 일이다. 감사 로그(Task 9)가 선택기를
갖는 것과 같은 이유다.

- [ ] **Step 4: 게이트와 커밋**

```bash
cd frontend && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit && npm test && npm run build
cd .. && git add frontend/app
git commit -m "설명 면을 나누고 문서 화면을 가시성 표로 줄였다"
```

---

## Task 7: 관리자 면과 낡은 껍데기 제거

**Files:**
- Create: `frontend/app/(admin)/layout.tsx`
- Move: `frontend/app/(app)/admin` → `frontend/app/(admin)/admin`
- Delete: `frontend/app/(app)/logs/page.tsx` (Task 9 가 다시 만든다)
- Delete: `frontend/app/(app)/layout.tsx`, `frontend/components/Sidebar.tsx`
- Modify: `frontend/lib/types.ts` (`NAV_ITEMS` 제거)

- [ ] **Step 1: 관리자 레이아웃을 만든다**

```tsx
import { redirect } from "next/navigation";
import { auth, signOutAction } from "@/auth";
import { roleFor } from "@/lib/session";
import { guard, navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import Header from "@/components/Header";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.email) redirect("/");
  const role = roleFor(session.user.email);
  // 레이아웃이 막지만 각 페이지도 자기 몫의 확인을 유지한다 — admin/page.tsx
  // 의 주석이 적어둔 이유(주소창·콘솔) 그대로다. 두 벌인 것이 맞다.
  if (guard({ surface: "admin", hasPersona: false, role }) === "to-hub") redirect("/");
  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "236px 1fr", background: "var(--color-bg)" }}>
      <SurfaceNav items={navFor("admin")} 부제="운영 · 감사" />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header email={session.user.email} role={role} signOutAction={signOutAction} />
        <div style={{ padding: "28px 40px 56px" }}>{children}</div>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: 옮기고 지운다**

```bash
git mv "frontend/app/(app)/admin" "frontend/app/(admin)/admin"
git rm -r "frontend/app/(app)/logs" "frontend/app/(app)/layout.tsx"
git rm frontend/components/Sidebar.tsx
```

`lib/types.ts` 에서 **`NAV_ITEMS` 상수만 지운다.** `NavItem` 타입은 남긴다 —
`surface.ts` 의 `NAV` 와 `SurfaceNav`·`Header` 의 prop 이 계속 쓴다.

이 시점에 `NAV_ITEMS` 를 쓰는 곳은 없다: `Sidebar.tsx` 는 이 태스크에서
지웠고, `Header.tsx` 는 Task 6 에서 배열을 prop 으로 받도록 고쳤다.
확인:

```bash
grep -rn "NAV_ITEMS" frontend/ --include="*.ts*" || echo "사용처 없음"
```

**낡은 껍데기가 사라졌는지 확인한다:**

```bash
grep -rn "적재는 W4 에서 채웁니다" frontend/ || echo "사라졌다"
```

- [ ] **Step 3: member 로 막히는지 확인한다**

`ADMIN_EMAILS` 를 비운 채 `npm run dev` 로 `/admin` 에 직접 들어가 `/` 로
튕기는 것을 확인하고 되돌린다.

- [ ] **Step 4: 게이트와 커밋**

```bash
cd frontend && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit && npm test && npm run build
cd .. && git add -A frontend
git commit -m "관리자 면을 나누고 낡은 감사 로그 껍데기를 지웠다"
```

---

## Task 8: 백엔드 `GET /log-events`

**Files:**
- Modify: `backend/api/main.py`, `backend/api/schemas.py`
- Create: `backend/tests/test_api_log_events.py`

**Interfaces:**
- Produces: `GET /log-events?persona=&event_type=&since=&limit=` →
  `list[LogEventView]`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api_log_events.py`. 기존 `tests/test_api.py` 의 스텁
방식을 그대로 따른다(`시크릿`·`헤더` 상수, `스텁주체저장소`).

```python
"""GET /log-events — 주체의 눈으로 본 로그.

**권한 없는 조회 경로를 만들지 않는다.** LogSearch.query 가 Principal 을
필수로 받는 이유(core/ports.py: "권한 없는 조회를 호출할 방법이 없다")가
HTTP 계층에서도 유지되는지를 이 파일이 지킨다.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import build_app
from core.types import LogEvent, Principal

시크릿 = "test-secret-abc123"
헤더 = {"X-Backend-Secret": 시크릿}


class 스텁로그검색:
    def __init__(self):
        self.받은_주체 = []

    def query(self, principal, event_type, since, limit):
        self.받은_주체.append(principal)
        return []


class 스텁주체저장소:
    def find(self, name):
        return Principal(department="개발팀", clearance=1) if name == "김개발" else None


@pytest.fixture
def 검색():
    return 스텁로그검색()


@pytest.fixture
def client(검색, monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    app = build_app(lambda: None, 스텁주체저장소(), 로그검색=검색)
    return TestClient(app)


def test_시크릿_없이는_401(client):
    assert client.get("/log-events?persona=김개발").status_code == 401


def test_알_수_없는_페르소나는_400(client):
    r = client.get("/log-events?persona=없는사람", headers=헤더)
    assert r.status_code == 400


def test_주체가_검색기까지_전달된다(client, 검색):
    """**이 테스트가 이 엔드포인트의 핵심이다.**

    주체 없이 조회하는 경로가 생기면 그것이 곧 우회 경로다. 검색기가
    받은 주체가 principals 테이블에서 번역된 것인지를 본다.
    """
    client.get("/log-events?persona=김개발", headers=헤더)
    assert 검색.받은_주체 == [Principal(department="개발팀", clearance=1)]
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_api_log_events.py`
Expected: FAIL — `build_app() got an unexpected keyword argument '로그검색'`

- [ ] **Step 3: 스키마를 더한다**

`backend/api/schemas.py`:

```python
class LogEventView(BaseModel):
    id: int
    ts: datetime | None
    host: str
    process: str | None
    event_type: str
    raw: str
```

`raw` 를 담는 것은 이 화면이 **로그 원문을 보여주는 화면**이기 때문이다.
문서 쪽과 다르다 — 문서는 본문을 감추지만(제목만으로 존재가 드러난다),
로그는 이미 권한 필터를 통과한 이벤트만 오므로 원문이 그 주체의 것이다.

- [ ] **Step 4: 엔드포인트를 더한다**

`backend/api/main.py` 의 `build_app` 에 `로그검색: LogSearch | None = None`
인자를 더하고:

```python
    @app.get("/log-events", dependencies=[Depends(시크릿_검사)])
    def log_events(
        persona: str,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[LogEventView]:
        """**주체 없이 부를 수 없다.** persona 가 필수 쿼리 인자인 이유가
        그것이다 — 기본값을 주면 그 기본값이 곧 권한 우회 경로가 된다.
        """
        if 로그검색 is None:
            raise HTTPException(status_code=503, detail="로그 검색 준비되지 않음")
        principal = 주체저장소.find(persona)
        if principal is None:
            raise HTTPException(status_code=400, detail="알 수 없는 페르소나")
        return [
            LogEventView(id=e.id, ts=e.ts, host=e.host, process=e.process,
                         event_type=e.event_type, raw=e.raw)
            for e in 로그검색.query(principal, event_type, since, limit)
        ]
```

`api/deps.py` 에서 `PgLogSearch(conn)` 를 넘긴다.

- [ ] **Step 5: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_api_log_events.py -v`
Expected: PASS 3건

- [ ] **Step 6: 실제 코퍼스에서 주체별로 갈리는지 확인한다**

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml \
  -f docker-compose.tunnel.yml up -d --build secu-backend
SEC=$(grep '^BACKEND_SHARED_SECRET=' .env | cut -d= -f2)
for p in 김개발 박인사 최임원; do
  echo -n "$p: "
  curl -s "localhost:18080/log-events?persona=$p&limit=100" -H "X-Backend-Secret: $SEC" \
    | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
done
```

Expected: 세 수가 **같지 않다.** 같으면 화면이 보여줄 것이 없으므로 그때는
`data/hosts.json` 의 권한 배치를 확인한다.

- [ ] **Step 7: 게이트와 커밋**

```bash
cd backend && .venv/bin/python -m pytest -q -m "not db" && .venv/bin/python -m pytest -q -m db \
  && .venv/bin/python -m pytest -q -m corpus && .venv/bin/python -m ruff check . \
  && .venv/bin/python -m ruff format --check .
cd .. && git add backend/api backend/tests/test_api_log_events.py
git commit -m "주체의 눈으로 보는 로그 조회 엔드포인트를 더했다"
```

---

## Task 9: 감사 로그 화면

**Files:**
- Create: `frontend/app/api/log-events/route.ts`
- Create: `frontend/app/(admin)/logs/page.tsx`

**Interfaces:**
- Consumes: `GET /log-events` (Task 8)

- [ ] **Step 1: BFF 를 만든다**

`frontend/app/api/access-log/route.ts` 의 모양을 그대로 따른다 — 세션 확인
뒤 `roleFor` 로 관리자까지 확인한다.

```ts
import { auth } from "@/auth";
import { roleFor } from "@/lib/session";

// 관리자 전용 데이터이므로 로그인만으로는 부족하다 — /api/access-log 와
// 같은 이유, 같은 모양이다.
export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.email) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }
  if (roleFor(session.user.email) !== "admin") {
    return Response.json({ error: "권한이 없습니다" }, { status: 403 });
  }
  const persona = new URL(req.url).searchParams.get("persona") ?? "";
  const upstream = await fetch(
    `${process.env.BACKEND_URL}/log-events?persona=${encodeURIComponent(persona)}&limit=100`,
    { headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" } }
  );
  if (!upstream.ok) {
    return Response.json({ error: "백엔드 오류", status: upstream.status }, { status: upstream.status });
  }
  return Response.json(await upstream.json());
}
```

- [ ] **Step 2: 화면을 만든다**

주체 선택기가 **이 화면 안에** 있다. 직원 면에서 걷어낸 것과 모순되지
않는 이유를 주석에 적는다.

```tsx
"use client";

import { useEffect, useState } from "react";
import Blueprint from "@/components/Blueprint";
import PersonaSegment, { type Principal } from "@/components/PersonaSegment";

type LogEvent = { id: number; ts: string | null; host: string; process: string | null;
  event_type: string; raw: string };

// 이 화면에 주체 선택기가 있는 이유: 저장소에 **권한 필터를 우회하는 로그
// 조회 경로가 없다**(core/ports.py 의 LogSearch.query 가 Principal 을 필수로
// 받는다). 관리자 편의로 하나 만들면 그것이 이 프로젝트가 테스트로 막아온
// 그 경로다. 직원 면에서 선택기를 걷어낸 것과 모순되지 않는다 — 직원 면은
// 한 사람이 되어보는 곳이고 여기는 장치를 들여다보는 곳이라 도구가 다르다.
export default function LogsPage() {
  const [계정, set계정] = useState<Principal[]>([]);
  const [주체, set주체] = useState("");
  const [이벤트, set이벤트] = useState<LogEvent[] | null>(null);

  useEffect(() => {
    fetch("/api/principals").then((r) => r.json()).then((p: Principal[]) => {
      set계정(p);
      set주체(p[0]?.name ?? "");
    });
  }, []);

  useEffect(() => {
    if (!주체) return;
    set이벤트(null);
    fetch(`/api/log-events?persona=${encodeURIComponent(주체)}`)
      .then((r) => r.json())
      .then(set이벤트)
      .catch(() => set이벤트([]));
  }, [주체]);

  return (
    <div style={{ maxWidth: 1100, display: "flex", flexDirection: "column", gap: 18 }}>
      <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7, color: "var(--color-neutral-700)" }}>
        주체를 바꾸면 보이는 이벤트가 달라집니다. 문서에 걸린 것과{" "}
        <strong>같은 판정 함수</strong>가 로그에도 걸립니다 —
        <code> core/access/visibility.py</code> 의 <code>visible()</code> 하나입니다.
      </p>
      <PersonaSegment personas={계정} value={주체} onChange={set주체} />
      {이벤트 === null ? (
        <p style={{ fontSize: 13 }}>불러오는 중…</p>
      ) : (
        <>
          <div style={{ fontSize: 13 }}>{주체} 가 볼 수 있는 이벤트 {이벤트.length}건</div>
          {이벤트.map((e) => (
            <Blueprint key={e.id} className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: "var(--color-neutral-700)" }}>
                {e.ts ?? "시각 없음"} · {e.host} · {e.event_type}
              </div>
              <div style={{ fontFamily: "ui-monospace,monospace", fontSize: 12.5, marginTop: 6 }}>{e.raw}</div>
            </Blueprint>
          ))}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 브라우저에서 확인한다**

관리자로 `/logs` 를 열고 주체를 바꿔 **건수가 실제로 달라지는지** 본다.
Task 8 Step 6 에서 잰 수와 같아야 한다.

- [ ] **Step 4: member 가 막히는지 확인한다**

`ADMIN_EMAILS` 를 비운 채 `/api/log-events?persona=김개발` 을 호출해 403 이
오는 것을 확인하고 되돌린다.

- [ ] **Step 5: 게이트와 커밋**

```bash
cd frontend && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit && npm test && npm run build
cd .. && git add frontend/app
git commit -m "감사 로그를 주체의 눈으로 보는 화면으로 만들었다"
```

---

## 완료 조건

- [ ] `pytest -m "not db"` · `-m db` · `-m corpus` · `ruff check` · `ruff format --check` 통과
- [ ] `npm test` · `npx tsc --noEmit` · `npm run build` 통과
- [ ] 로그인 직후 허브가 뜨고 세 직원 카드와 설명 입구가 보인다
- [ ] 직원을 고르면 그 사람의 헤더가 붙은 직원 면으로 들어간다
- [ ] 새로고침해도 그 직원이 유지된다
- [ ] "나가기"를 누르면 허브로 돌아와 다시 고를 수 있다
- [ ] 직원 면에 페르소나 선택기가 없다
- [ ] "내 문서" 목록 길이가 직원에 따라 달라진다
- [ ] 헤더의 시연 고지가 상시 보이고 펼치면 설명이 나온다
- [ ] 쿠키 없이 `/ask` 로 직접 들어가면 허브로 보내진다
- [ ] `member` 로 `/admin`·`/logs` URL 에 직접 들어가면 되돌려진다
- [ ] `/api/log-events` 가 member 에게 403
- [ ] 감사 로그가 실제 이벤트를 보여주고 주체를 바꾸면 건수가 갈린다
- [ ] **`grep -rn "권한_WHERE" backend` 결과에 새 우회 경로가 없다**
- [ ] 허브가 좁은 화면에서 카드를 세로로 쌓는다
- [ ] `grep -rn "적재는 W4 에서 채웁니다" frontend/` 가 비어 있다

## 다음 계획으로 넘길 것

- **전면 반응형** — 허브를 뺀 나머지 화면. 앱 셸의 `236px 1fr` 고정이 뿌리다
- **컴포넌트 테스트 도구** — 이 계획은 판정 로직을 `lib/` 로 빼는 것까지만 한다
- **`draft_report`·`verify_clauses`** — 상위 spec §7
