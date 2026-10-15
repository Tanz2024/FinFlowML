import { NextResponse } from "next/server";
const secureCookies = process.env.AUTH_COOKIE_SECURE === "true";
export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (origin && host) {
    try {
      if (new URL(origin).host !== host) return new NextResponse("Cross-origin request rejected", { status: 403 });
    } catch {
      return new NextResponse("Cross-origin request rejected", { status: 403 });
    }
  }
  const response = new NextResponse(null, { status: 303, headers: { Location: "/login" } });
  for (const name of ["finflow_token", "finflow_role"]) response.cookies.set(name, "", { httpOnly: name === "finflow_token", sameSite: "lax", secure: secureCookies, path: "/", maxAge: 0 });
  return response;
}
