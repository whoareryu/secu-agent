// 어느 브라우저가 남긴 열람 기록인지를 가르는 값.
//
// **권한이 아니다.** 이 값으로 열리는 것은 "그 세션이 던진 질의의 원문"
// 하나뿐이고, 문서·로그 가시성은 여전히 페르소나의 등급·부서가 정한다.
// 위조해도 얻는 것이 없다시피 하지만, 난수라 남의 값을 알 방법도 없다.
//
// 이메일·이름과 잇지 않는다. 서버는 이 값이 누구인지 모른다.
export const VISITOR_COOKIE = "sa_vid";

export function newVisitorId(): string {
  return crypto.randomUUID().replaceAll("-", "");
}
