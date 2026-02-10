import "./globals.css";
import { ThemeToggle } from "../components/ThemeToggle";

export const metadata = {
  title: "SportsBank Pro",
  description: "Dashboard de gestão de banca esportiva",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap"
        />
      </head>
      <body style={{ fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif" }}>
        <ThemeToggle />
        {children}
      </body>
    </html>
  );
}
