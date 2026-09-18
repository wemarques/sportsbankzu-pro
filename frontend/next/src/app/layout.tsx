import "./globals.css";
import { Zilla_Slab, Source_Sans_3 } from "next/font/google";
import { ThemeProvider } from "../components/theme-provider";
import { SessionProvider } from "../components/SessionProvider";
import { Navegacao } from "@/components/nav/Navegacao";
import { AncoraDoHash } from "@/components/nav/AncoraDoHash";

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
            <div className="min-h-screen bg-[var(--sb-tinta)] lg:flex">
              <AncoraDoHash />
              <Navegacao />
              <div className="flex-1 pb-16 lg:pb-0">{children}</div>
            </div>
          </ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
