import { NextResponse } from "next/server";
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
  const response = NextResponse.redirect(new URL("/login", request.url), 303);
  for (const name of ["finflow_token", "finflow_role"]) response.cookies.set(name, "", { httpOnly: name === "finflow_token", sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 0 });
  return response;
}
