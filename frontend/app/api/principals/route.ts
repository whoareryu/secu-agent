import { auth } from "@/auth";

// 질의 화면의 페르소나 세그먼트가 부르는 BFF. 세 페르소나를 하드코딩하지
// 않기 위해 백엔드 principals 테이블을 그대로 중계한다. 백엔드 주소도
// 공유 시크릿도 브라우저에 내려가지 않는다.
export async function GET() {
  const session = await auth();
  if (!session) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }

  const upstream = await fetch(`${process.env.BACKEND_URL}/principals`, {
    headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" },
  });

  if (!upstream.ok) {
    return Response.json(
      { error: "백엔드 오류", status: upstream.status },
      { status: upstream.status }
    );
  }
  return Response.json(await upstream.json());
}
