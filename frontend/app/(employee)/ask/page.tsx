import { signInAction } from "@/auth";
import AskClient from "./AskClient";

// signInAction 은 "use server" 함수라 클라이언트 컴포넌트(AskClient)가 직접
// import 할 수 없다 — auth.ts 가 NextAuth · next/headers 를 끌어오므로 클라
// 번들에 섞이면 빌드가 깨진다. 그래서 이 파일은 서버 컴포넌트로 남기고,
// 액션만 prop 으로 내려준다(components/SignIn.tsx 와 같은 모양).
export default function AskPage() {
  return <AskClient signInAction={signInAction} />;
}
