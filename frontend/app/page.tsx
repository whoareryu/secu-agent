import { auth, signIn, signOut } from "@/auth";
import AskForm from "@/components/AskForm";

export default async function Home() {
  const session = await auth();

  if (!session) {
    return (
      <main>
        <h1>Secu-Agent</h1>
        <p>부서·등급에 따라 검색 범위가 달라지는 사내보안 규정 에이전트입니다.</p>
        <form action={async () => { "use server"; await signIn("google"); }}>
          <button type="submit">구글로 로그인</button>
        </form>
      </main>
    );
  }

  return (
    <main>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Secu-Agent</h1>
        <form action={async () => { "use server"; await signOut(); }}>
          <button type="submit">로그아웃</button>
        </form>
      </header>
      <AskForm />
    </main>
  );
}
