import { redirect } from "next/navigation";
import { auth, signOutAction } from "@/auth";
import { roleFor } from "@/lib/session";
import { guard, navFor } from "@/lib/surface";
import SurfaceNav from "@/components/SurfaceNav";
import Header from "@/components/Header";

// 레이아웃이 막지만 각 페이지도 자기 몫의 확인을 유지한다 — admin/page.tsx
// 의 주석이 적어둔 이유(주소창·콘솔) 그대로다. 두 벌인 것이 맞다.
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.email) redirect("/");
  const role = roleFor(session.user.email);
  if (guard({ surface: "admin", hasPersona: false, role }) === "to-hub") redirect("/");
  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "236px 1fr", background: "var(--color-bg)" }}>
      <SurfaceNav items={navFor("admin")} 부제="운영 · 감사" />
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header email={session.user.email} role={role} signOutAction={signOutAction} items={navFor("admin")} />
        <div style={{ padding: "28px 40px 56px" }}>{children}</div>
      </main>
    </div>
  );
}
