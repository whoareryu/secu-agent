import { auth } from "@/auth";

// 문서 화면이 부르는 BFF. 백엔드 /documents 는 권한 필터 없이 전부 돌려준다
// (이 화면 자체가 "규칙이 어떻게 적용되는지"를 보여주는 자리라서). 백엔드
// 주소도 공유 시크릿도 브라우저에 내려가지 않는다.
export async function GET() {
  const session = await auth();
  if (!session) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }

  const upstream = await fetch(`${process.env.BACKEND_URL}/documents`, {
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
