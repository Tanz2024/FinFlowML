import { cookies } from "next/headers";
import { NextResponse } from "next/server";
export async function POST(request: Request){const origin=request.headers.get("origin");const host=request.headers.get("host");if(origin&&host&&new URL(origin).host!==host)return NextResponse.json({detail:"Cross-origin request rejected"},{status:403});const response=NextResponse.json({ok:true});response.cookies.delete("finflow_token");response.cookies.delete("finflow_role");return response}
