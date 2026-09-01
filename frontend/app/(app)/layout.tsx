import { redirect } from "next/navigation";
import { auth, signOutAction } from "@/auth";
import { roleFor } from "@/lib/session";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

// 앱 셸: 사이드바 + 헤더. 관리자 role 은 이메일 알리스트로 서버가 정한다
// (frontend/lib/session.ts) — 로그인 화면에서 고른 값이 아니다.
export default async function AppShellLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.email) {
    redirect("/");
  }

  const role = roleFor(session.user.email);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "236px 1fr",
        background: "var(--color-bg)",
      }}
    >
      <Sidebar role={role} />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header email={session.user.email} role={role} signOutAction={signOutAction} />
        <div style={{ padding: "28px 40px 56px" }}>{children}</div>
      </main>
    </div>
  );
}
