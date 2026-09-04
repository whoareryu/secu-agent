import { cookies } from "next/headers";
import { PERSONA_COOKIE } from "@/lib/persona";

// 지금 어느 직원으로 보고 있는지 — 설명·관리자 면의 주체 선택기가
// 첫 값을 여기서 가져온다.
//
// 라우트가 필요한 이유: 페르소나 쿠키는 httpOnly 다(app/page.tsx). 그래서
// 클라이언트 컴포넌트가 직접 읽을 수 없다. 쿠키를 httpOnly 가 아니게
// 바꾸는 쪽이 아니라 라우트를 더하는 쪽을 고른다 — 쿠키를 스크립트가
// 읽을 수 있게 만들면 스크립트가 **쓸** 수도 있게 되고, 그때 페르소나는
// 서버가 정하는 값이 아니라 브라우저가 정하는 값이 된다.
//
// 이름만 돌려준다. 부서·등급을 여기서 실어 보내면 그것이 api/schemas.py
// 가 막아둔 사칭 경로의 프론트엔드 판본이 된다 — 호출부는 이름을
// /api/principals 의 목록과 대조해서 쓴다(lib/persona.ts 의 personaFrom).
//
// 세션 검사가 있었는데 걷었다 — 페르소나는 로그인과 무관하게 허브에서 누구나
// 고르고(스펙 §2.2), 이 라우트는 그 사람이 방금 자기 브라우저에 심은 쿠키를
// 되읽어 줄 뿐이다. 남의 값을 볼 수 있게 되는 것이 아니다: 쿠키는 요청을 보낸
// 브라우저의 것뿐이다. 쓰기도 아니다 — 이 파일에는 GET 밖에 없고 쿠키를 심는
// 것은 허브의 서버 액션이다(app/page.tsx).
export async function GET() {
  const jar = await cookies();
  return Response.json({ name: jar.get(PERSONA_COOKIE)?.value ?? null });
}
