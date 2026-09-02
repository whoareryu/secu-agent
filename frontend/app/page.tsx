import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { auth, signInAction } from "@/auth";
import SignIn from "@/components/SignIn";
import Hub from "@/components/Hub";
import { PERSONA_COOKIE } from "@/lib/persona";
import type { Principal } from "@/components/PersonaSegment";

// 서버 컴포넌트이므로 BFF 를 거치지 않고 백엔드를 직접 부른다. BFF 라우트가
// 있는 이유는 브라우저가 시크릿을 가질 수 없어서이고, 여기는 서버다.
async function principals(): Promise<Principal[]> {
  const r = await fetch(`${process.env.BACKEND_URL}/principals`, {
    headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`principals ${r.status}`);
  return r.json();
}

export default async function Home() {
  const session = await auth();
  if (!session?.user?.email) {
    return <SignIn signInAction={signInAction} />;
  }

  async function 선택하기(formData: FormData) {
    "use server";
    const name = String(formData.get("persona") ?? "");
    const jar = await cookies();
    // httpOnly 로 둔다. 클라이언트 자바스크립트가 읽을 이유가 없고,
    // 읽을 수 없으면 이 값이 화면 상태로 새어나가 두 벌이 되는 일도 없다.
    jar.set(PERSONA_COOKIE, name, { httpOnly: true, sameSite: "lax", path: "/" });
    redirect("/ask");
  }

  return <Hub personas={await principals()} 선택하기={선택하기} />;
}
