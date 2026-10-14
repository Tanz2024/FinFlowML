import { redirect } from "next/navigation";
import { cookies } from "next/headers";
export default function Home(){if(!cookies().get("finflow_token"))redirect("/login");redirect("/dashboard")}
