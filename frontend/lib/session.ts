export type Role = "member" | "admin";

// 관리자 알리스트. 비어 있으면 아무도 관리자가 아니다 — 기본값이 "모두 관리자"
// 가 되면 안 된다.
//
// 모듈 최상단이 아니라 호출마다 읽는다. 최상단에서 읽으면 값이 모듈 로드
// 시점에 굳어 버려서, 그 값이 무엇이었는지에 따라 게이트가 달라지는데도
// 테스트가 알리스트를 바꿔가며 경계를 확인할 방법이 없다. rate-limit.ts 가
// 같은 이유로 같은 모양을 쓴다.
function adminEmails(): string[] {
  return (process.env.ADMIN_EMAILS ?? "")
    .split(",").map(s => s.trim()).filter(Boolean);
}

export function roleFor(email: string | null | undefined): Role {
  return email && adminEmails().includes(email) ? "admin" : "member";
}
