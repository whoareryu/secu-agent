"use client";

import { useState } from "react";
import AskPanel from "@/components/AskPanel";
import RightRail from "@/components/RightRail";

// 페르소나는 이 화면이 모른다 — 셸이 쿠키로 정하고 BFF 가 쿠키에서 읽는다.
//
// signInAction 은 서버 액션(frontend/auth.ts)이라 클라이언트 컴포넌트가
// 직접 import 할 수 없다 — 이 컴포넌트를 렌더하는 서버 컴포넌트(page.tsx)가
// prop 으로 내려준다(components/Header.tsx 와 같은 모양).
export default function AskClient({ signInAction }: { signInAction: () => Promise<void> }) {
  const [query, setQuery] = useState("");
  return (
    <div className="ask-layout">
      <AskPanel query={query} onQueryChange={setQuery} signInAction={signInAction} />
      <RightRail query={query} onSelectSample={setQuery} />
    </div>
  );
}
