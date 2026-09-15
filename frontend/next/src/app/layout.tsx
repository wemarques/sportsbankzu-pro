import "./globals.css";
import "@/styles/scoretabs-dashboard.css";
import "@/styles/match-detail-card.css";
import { Zilla_Slab, Source_Sans_3 } from "next/font/google";
import { ThemeProvider } from "../components/theme-provider";
import { ThemeToggle } from "../components/ThemeToggle";
import { SessionProvider } from "../components/SessionProvider";

const slab = Zilla_Slab({ subsets: ["latin"], weight: ["600", "700"], variable: "--font-slab", display: "swap" });
const sans = Source_Sans_3({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-sans", display: "swap" });

export const metadata = {
  title: "SportsBankZU Pro",
  description: "Dashboard de análise esportiva profissional",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning className={`${slab.variable} ${sans.variable}`}>
      <body>
        <SessionProvider>
          <ThemeProvider>
            <ThemeToggle />
            {children}
          </ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
