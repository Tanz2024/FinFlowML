import { cookies } from "next/headers";
import { NextResponse } from "next/server";
export async function POST(){const response=NextResponse.json({ok:true});response.cookies.delete("finflow_token");response.cookies.delete("finflow_role");return response}
