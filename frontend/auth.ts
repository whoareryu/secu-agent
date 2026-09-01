import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
});

// 클라이언트 컴포넌트(SignIn, Header)는 "use server" 함수를 직접 정의할 수
// 없으므로, 서버 액션을 여기서 내보내 폼의 action 으로 그대로 넘긴다.
export async function signInAction() {
  "use server";
  await signIn("google");
}

export async function signOutAction() {
  "use server";
  await signOut();
}
