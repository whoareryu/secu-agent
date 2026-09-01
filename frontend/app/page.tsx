import { redirect } from "next/navigation";
import { auth, signInAction } from "@/auth";
import SignIn from "@/components/SignIn";

export default async function Home() {
  const session = await auth();

  if (!session?.user?.email) {
    return <SignIn signInAction={signInAction} />;
  }

  // 로그인된 사용자는 /ask 로 보낸다. 여기서 앱 셸을 직접 그리면 /ask 와
  // 렌더 경로가 둘로 갈리고, 사이드바가 어느 쪽을 가리키든 다른 쪽은 죽는다.
  redirect("/ask");
}
