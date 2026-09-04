import { auth } from "@/auth";

// /how 화면이 부르는 BFF. 관리자 전용이 아니다 — 이 화면 자체가 "동작
// 원리를 설명"이므로 로그인한 사용자 누구나 돌려볼 수 있어야 한다.
//
// **이 경로가 안전한 이유는 "본문을 안 준다"가 아니다.** 응답은 세 계정의
// 조항 코드를 함께 담고, 조항 코드는 그 문서가 존재한다는 것을 확인해 준다 —
// 이 프로젝트가 감춘다고 주장하는 바로 그 신호다. 안전한 이유는 **질의를
// 호출자가 정할 수 없다**는 것 하나다. 백엔드가 고정 목록의 인덱스만 받으므로
// 임의 주제로 등급 밖 조항을 열거할 손잡이가 없다(backend/demo/compare.py 의
// 시연_질의). 여기에 자유 문자열을 되살리면 이 화면은 그 즉시 존재 오라클이
// 된다 — 로그인은 요금 게이트이지 권한이 아니라서 그 앞을 막지 못한다.
//
// 본문을 그대로 중계한다. 인덱스 범위 검사는 백엔드가 한다(422).
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
