export type Role = "member" | "admin";

// 관리자 알리스트. 비어 있으면 아무도 관리자가 아니다 — 기본값이 "모두 관리자"
// 가 되면 안 된다.
const ADMIN_EMAILS = (process.env.ADMIN_EMAILS ?? "")
  .split(",").map(s => s.trim()).filter(Boolean);

export function roleFor(email: string | null | undefined): Role {
  return email && ADMIN_EMAILS.includes(email) ? "admin" : "member";
}
