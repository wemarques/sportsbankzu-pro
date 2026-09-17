import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// TODO #136: reativar auth quando RDS/Vercel estiver configurado
// Por enquanto, todas as rotas são públicas. Sem verificação de token.

const COOKIE_VISITOU = "sbz_visitou";
const TTL_VISITOU_S = 60 * 60 * 24 * 180; // 180 dias — #257, decisão de projeto

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const visitou = req.cookies.get(COOKIE_VISITOU)?.value === "1";

  // #257: "/" é o hero só na primeira visita/deslogado (spec §3). Quem já
  // visitou vai direto para o feed, sem flash do hero (decisão no server).
  if (pathname === "/") {
    if (visitou) {
      const resposta = NextResponse.redirect(new URL("/jogos", req.url));
      resposta.cookies.set(COOKIE_VISITOU, "1", { maxAge: TTL_VISITOU_S, path: "/", sameSite: "lax" });
      return resposta;
    }
    const resposta = NextResponse.next();
    resposta.cookies.set(COOKIE_VISITOU, "1", { maxAge: TTL_VISITOU_S, path: "/", sameSite: "lax" });
    return resposta;
  }

  // Qualquer visita a /jogos também marca "já visitou" — quem chega direto
  // por link compartilhado não vê o hero na próxima vez que abrir "/".
  if (pathname.startsWith("/jogos") && !visitou) {
    const resposta = NextResponse.next();
    resposta.cookies.set(COOKIE_VISITOU, "1", { maxAge: TTL_VISITOU_S, path: "/", sameSite: "lax" });
    return resposta;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|logos).*)"],
};
