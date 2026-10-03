import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";

export const metadata: Metadata = {
  title: "Financial Intelligence Terminal",
  description: "Analyze real-time market data and macro impacts.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full bg-white">
      <body className="h-full bg-white text-gray-900 antialiased selection:bg-gray-200">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
