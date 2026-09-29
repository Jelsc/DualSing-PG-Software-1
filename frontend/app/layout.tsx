import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DualSign Administration",
  description: "Local administrative shell for DualSign IA.",
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
