import "./_ds/industry.css";

export const metadata = { title: "Secu-Agent" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
