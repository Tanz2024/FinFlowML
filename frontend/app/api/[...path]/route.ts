import { cookies } from "next/headers";
import { NextResponse } from "next/server";
const backend=process.env.BACKEND_URL??"http://127.0.0.1:8000";
async function proxy(request:Request,{params}:{params:Promise<{path:string[]}>}){
  if (["POST", "PATCH", "PUT", "DELETE"].includes(request.method)) {
    const origin = request.headers.get("origin"); const host = request.headers.get("host");
    if (origin && host && new URL(origin).host !== host) return NextResponse.json({detail:"Cross-origin request rejected"},{status:403});
  }
  const token=(await cookies()).get("finflow_token")?.value;
  if(!token)return NextResponse.json({detail:"authentication required"},{status:401});
  const url=`${backend}/${(await params).path.join("/")}${new URL(request.url).search}`;
  const headers=new Headers(request.headers);headers.delete("host");headers.delete("cookie");headers.set("Authorization",`Bearer ${token}`);
  const isMultipart = headers.get("content-type")?.startsWith("multipart/form-data") ?? false;
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  if (isMultipart) headers.delete("content-length");
  const response=await fetch(url,{method:request.method,headers,body});
  const result=new NextResponse(response.body,{status:response.status,headers:{"content-type":response.headers.get("content-type")??"application/json"}});
  if(response.status===401){result.cookies.delete("finflow_token");result.cookies.delete("finflow_role");}return result;
}
export const GET=proxy;export const POST=proxy;export const PATCH=proxy;
