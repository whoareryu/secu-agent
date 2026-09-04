import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { cookies } from "next/headers";
import { PERSONA_COOKIE } from "@/lib/persona";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
});

// 클라이언트 컴포넌트(Header, AskPanel)는 "use server" 함수를 직접 정의할 수
// 없으므로, 서버 액션을 여기서 내보내 폼의 action 으로 그대로 넘긴다.
export async function signInAction() {
  "use server";
  await signIn("google");
}

// 로그아웃은 페르소나 쿠키도 함께 지운다(W6 스펙 §2.6). signOut() 만 부르면
// 쿠키가 남아, 같은 브라우저에서 **다른 구글 계정으로** 다시 로그인한 사람이
// 앞사람이 고른 페르소나를 그대로 물려받는다. 권한 상승은 아니다 — 페르소나는
// 허브에서 누구나 자유롭게 고른다 — 하지만 로그인 직후 화면이 "고른 적 없는
// 계정으로 보는 중" 이 된다.
//
// signOut() 앞에 둔다. signOut() 은 리다이렉트를 던지므로 뒤에 두면 실행되지
// 않는다.
export async function signOutAction() {
  "use server";
  const jar = await cookies();
  jar.delete(PERSONA_COOKIE);
  await signOut();
}
