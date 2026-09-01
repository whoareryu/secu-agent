import { auth } from "@/auth";
import { check } from "@/lib/rate-limit";

// 브라우저가 닿는 유일한 엔드포인트다. 백엔드 주소도 시크릿도
// 브라우저에 내려가지 않는다.
export async function POST(req: Request) {
  const session = await auth();
  if (!session) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }

  // LLM 을 부르기 전에 상한을 검사한다 — 이미 부른 뒤에 검사하면 요금
  // 폭주를 막지 못한다.
  const limit = check(session.user?.email ?? "");
  if (!limit.allowed) {
    return Response.json({ error: "오늘 사용 가능한 질의를 모두 썼습니다", remaining: 0 }, { status: 429 });
  }

  let query, persona;
  try {
    ({ query, persona } = await req.json());
  } catch {
    return Response.json({ error: "잘못된 요청 본문입니다" }, { status: 400 });
  }

  const upstream = await fetch(`${process.env.BACKEND_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "",
    },
    // 백엔드가 받는 것은 이 둘뿐이다. 세션에서 온 어떤 값도 등급으로
    // 번역되지 않는다 — 등급은 페르소나 이름으로만 정해진다.
    body: JSON.stringify({ query, persona }),
  });

  if (!upstream.ok) {
    return Response.json(
      { error: "백엔드 오류", status: upstream.status },
      { status: upstream.status }
    );
  }
  const data = await upstream.json();
  return Response.json({ ...data, remaining: limit.remaining });
}
