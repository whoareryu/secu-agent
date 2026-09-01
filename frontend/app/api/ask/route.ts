import { auth } from "@/auth";

// 브라우저가 닿는 유일한 엔드포인트다. 백엔드 주소도 시크릿도
// 브라우저에 내려가지 않는다.
export async function POST(req: Request) {
  const session = await auth();
  if (!session) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }

  const { query, persona } = await req.json();

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
  return Response.json(await upstream.json());
}
