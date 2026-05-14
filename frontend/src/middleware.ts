import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login"];

export default function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.includes(pathname) || pathname.startsWith("/_next") || pathname.includes(".")) {
    return NextResponse.next();
  }

  const token = request.cookies.get("token")?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!login|_next|favicon\\.ico|.*\\..*).*)"],
};
