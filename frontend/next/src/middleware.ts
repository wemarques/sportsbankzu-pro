import { getToken } from "next-auth/jwt";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_ROUTES = ["/login", "/register", "/api/auth"];
const ADMIN_ROUTES = ["/admin", "/audit", "/tools"];

export async function middleware(req: NextRequest) {
  // TODO #136: reativar quando RDS aceitar conexão do Vercel
  // Bypass temporário — todas as rotas públicas
  return NextResponse.next();

  /* Original auth logic (reativar acima):
  const path = req.nextUrl.pathname;

  if (PUBLIC_ROUTES.some((r) => path.startsWith(r))) return NextResponse.next();
  if (path.startsWith("/_next") || path.startsWith("/favicon") || path.startsWith("/logos")) return NextResponse.next();

  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });

  if (!token) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("callbackUrl", path);
    return NextResponse.redirect(loginUrl);
  }

  if (ADMIN_ROUTES.some((r) => path.startsWith(r)) && token.role !== "admin") {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  return NextResponse.next();
  */
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
