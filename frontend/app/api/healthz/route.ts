import { auth } from "@/auth";

// 사이드바의 GET /healthz 블록이 부르는 BFF. 백엔드 /healthz 는 시크릿이
// 필요 없지만, 브라우저가 백엔드 주소를 알지 못하도록 여기서 중계한다.
export async function GET() {
  const session = await auth();
  if (!session) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }

  const upstream = await fetch(`${process.env.BACKEND_URL}/healthz`);

  if (!upstream.ok) {
    return Response.json(
      { error: "백엔드 오류", status: upstream.status },
      { status: upstream.status }
    );
  }
  return Response.json(await upstream.json());
}
