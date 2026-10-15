import { cookies } from "next/headers";
import { NextResponse } from "next/server";
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const secureCookies = process.env.AUTH_COOKIE_SECURE === "true";
export async function POST(request: Request) {
  const origin = request.headers.get("origin"); const host = request.headers.get("host");
  if (origin && host && new URL(origin).host !== host) return NextResponse.json({ detail: "Cross-origin request rejected" }, { status: 403 });
  const response = await fetch(`${backend}/auth/login`, {method:"POST", headers:{"content-type":"application/json"}, body:await request.text()});
  const data = await response.json();
  if (!response.ok) return NextResponse.json(data, {status:response.status});
  const result = NextResponse.json({organization_id:data.organization_id, role:data.role, expires_in:data.expires_in});
  result.cookies.set("finflow_token", data.access_token, {httpOnly:true, sameSite:"lax", secure:secureCookies, maxAge:data.expires_in, path:"/"});
  result.cookies.set("finflow_role", data.role, {httpOnly:false, sameSite:"lax", secure:secureCookies, maxAge:data.expires_in, path:"/"});
  return result;
}
