import type { Principal } from "../components/PersonaSegment.tsx";
import type { Role } from "./surface.ts";

// 서버 컴포넌트이므로 BFF 를 거치지 않고 백엔드를 직접 부른다. BFF 라우트가
// 있는 이유는 브라우저가 시크릿을 가질 수 없어서이고, 여기는 서버다.
//
// 허브·직원 셸·관리자 셸 셋이 같은 목록을 필요로 한다. 셋으로 나뉘어 있던
// 것을 여기로 모은다 — 헤더 한 줄이나 cache 옵션이 한 곳에서만 바뀌면
// 어느 면은 캐시된 목록을, 어느 면은 새 목록을 보게 된다.
export async function principals(): Promise<Principal[]> {
  const r = await fetch(`${process.env.BACKEND_URL}/principals`, {
    headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`principals ${r.status}`);
  return r.json();
}

// 확정된 페르소나 이름을 역할로 옮긴다. 이름이 없거나 목록에 없으면
// "member" — 닫히는 방향이다.
//
// 이 기본값이 한 곳에 있어야 하는 이유는 guard() 가 한 곳에 있어야 하는
// 이유와 같다(surface.ts 의 머리 주석). 판정을 모아 두어도 그 **입력**을
// 면마다 따로 구하면 결함이 한 겹 아래로 옮겨갈 뿐이다 — 나중에 이 기본값을
// 조일 때 사본이 있으면 한 면에만 걸린다.
export function roleOf(목록: Principal[], name: string | null): Role {
  if (name === null) return "member";
  return 목록.find((p) => p.name === name)?.role ?? "member";
}
