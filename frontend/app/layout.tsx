import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DualSign",
  description: "DualSign internal operations and company vocabulary workspaces.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
