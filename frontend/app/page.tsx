import { redirect } from "next/navigation";
import { cookies } from "next/headers";
export default async function Home(){if(!(await cookies()).get("finflow_token"))redirect("/login");redirect("/dashboard")}
