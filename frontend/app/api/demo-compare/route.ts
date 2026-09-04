// /how 화면이 부르는 BFF. 관리자 전용이 아니다 — 이 화면 자체가 "동작
// 원리를 설명"이므로 **누구나** 돌려볼 수 있어야 한다. 세션 검사가 있었는데
// 걷었다(스펙 §2.2): 설명 면이 로그인 없이 열리는데 이 패널만 401 이면
// /how 의 ① 이 비로그인 방문자에게는 조용히 죽은 칸이 된다.
//
// **이 경로가 안전한 이유는 "본문을 안 준다"가 아니다.** 응답은 세 계정의
// 조항 코드를 함께 담고, 조항 코드는 그 문서가 존재한다는 것을 확인해 준다 —
// 이 프로젝트가 감춘다고 주장하는 바로 그 신호다. 안전한 이유는 **질의를
// 호출자가 정할 수 없다**는 것 하나다. 백엔드가 고정 목록의 인덱스만 받으므로
// 임의 주제로 등급 밖 조항을 열거할 손잡이가 없다(backend/demo/compare.py 의
// 시연_질의). 여기에 자유 문자열을 되살리면 이 화면은 그 즉시 존재 오라클이
// 된다 — 로그인은 요금 게이트이지 권한이 아니라서 그 앞을 막지 못한다.
// 그 문장이 세션 검사를 걷을 수 있는 근거이기도 하다: 이 경로를 지키는 것은
// 처음부터 로그인이 아니라 그 고정 목록이었다. 요금도 열리지 않는다 —
// backend/demo/compare.py 는 LLM 을 부르지 않는다(DB 조회와 임베딩 한 번).
//
// 본문을 그대로 중계한다. 인덱스 범위 검사는 백엔드가 한다(422).
export async function POST(req: Request) {
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
