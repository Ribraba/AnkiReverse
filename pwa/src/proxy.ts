import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

export async function middleware(req: NextRequest) {
  // Laisser passer la route qui pose le cookie démo
  if (req.nextUrl.pathname === "/demo") return NextResponse.next();

  // Laisser passer si le cookie démo est actif
  if (req.cookies.get("ankireverse_demo")?.value === "1") return NextResponse.next();

  // Sinon vérifier la session next-auth
  const token = await getToken({ req });
  if (!token) {
    const loginUrl = new URL("/login", req.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!login|api/auth|_next|favicon.ico|manifest.json|icon-|sw-push.js).*)",
  ],
};
