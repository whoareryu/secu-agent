import { auth } from "@/auth";

// /how 화면이 부르는 BFF. 관리자 전용이 아니다 — 이 화면 자체가 "동작
// 원리를 설명"이므로 로그인한 사용자 누구나 돌려볼 수 있어야 한다.
// 백엔드 POST /demo/compare 는 청크 본문도 없고 LLM 도 부르지 않으며
// 페르소나별 개수·조항 코드만 돌려준다 — 본문을 그대로 중계한다.
export async function POST(req: Request) {
  const session = await auth();
  if (!session) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }

  const upstream = await fetch(`${process.env.BACKEND_URL}/demo/compare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "",
    },
    body: await req.text(),
  });

  if (!upstream.ok) {
    return Response.json(
      { error: "백엔드 오류", status: upstream.status },
      { status: upstream.status }
    );
  }
  return Response.json(await upstream.json());
}
