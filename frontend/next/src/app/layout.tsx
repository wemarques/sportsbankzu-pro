import "./globals.css";
import "@/styles/match-detail-card.css";
import { Inter } from "next/font/google";
import { ThemeProvider } from "../components/theme-provider";
import { ThemeToggle } from "../components/ThemeToggle";

export const metadata = {
  title: "SportsBank Pro",
  description: "Dashboard de análise esportiva profissional",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider>
          <ThemeToggle />
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
