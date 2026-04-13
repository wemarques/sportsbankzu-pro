import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// TODO #136: reativar auth quando RDS/Vercel estiver configurado
// Por enquanto, todas as rotas são públicas. Sem verificação de token.

export function middleware(req: NextRequest) {
  // Redirect "/" to "/dashboard"
  if (req.nextUrl.pathname === "/") {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|logos).*)"],
};
