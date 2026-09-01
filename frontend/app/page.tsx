import { auth, signInAction } from "@/auth";
import SignIn from "@/components/SignIn";
import AskForm from "@/components/AskForm";
import AppShellLayout from "./(app)/layout";

export default async function Home() {
  const session = await auth();

  if (!session?.user?.email) {
    return <SignIn signInAction={signInAction} />;
  }

  // Ask 화면 자체를 다듬는 것은 다음 태스크의 몫이다 — 기존 컴포넌트를 셸
  // 안에 그대로 둔다.
  return (
    <AppShellLayout>
      <AskForm />
    </AppShellLayout>
  );
}
