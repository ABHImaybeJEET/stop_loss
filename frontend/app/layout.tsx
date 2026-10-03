import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { PortfolioProvider } from "@/context/PortfolioContext";
import PortfolioDialog from "@/components/portfolio/PortfolioDialog";

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
        <AuthProvider>
          <PortfolioProvider>
            {children}
            <PortfolioDialog />
          </PortfolioProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
