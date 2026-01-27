import "./globals.css";
import { Inter } from "next/font/google";
import { ThemeToggle } from "../components/ThemeToggle";

const inter = Inter({ subsets: ["latin"] });

export const metadata = {
  title: "SportsBank Pro",
  description: "Dashboard de gestão de banca esportiva",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className={inter.className}>
        <ThemeToggle />
        {children}
      </body>
    </html>
  );
}
