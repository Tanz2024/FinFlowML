"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname(); const router = useRouter(); const [role, setRole] = useState("");
  useEffect(() => setRole(document.cookie.match(/(?:^|; )finflow_role=([^;]+)/)?.[1] ?? ""), []);
  async function logout() { await fetch("/api/auth/logout", { method: "POST" }); router.push("/login"); }
  const canScan = role === "admin" || role === "reviewer";
  return <div className="min-h-screen"><aside className="sidebar fixed inset-y-0 left-0 hidden w-64 p-6 md:block"><p className="text-xl font-bold text-white">FinFlow<span className="text-blue-300">ML</span></p><p className="mt-1 text-xs text-slate-400">Finance operations</p><nav className="mt-10 space-y-2"><Link className={path === "/dashboard" ? "active" : ""} href="/dashboard">Dashboard</Link>{canScan && <Link className={path === "/scan" ? "active" : ""} href="/scan">Scan receipt</Link>}<Link className={path === "/pending" ? "active" : ""} href="/pending">Pending reviews</Link></nav><button onClick={logout} className="absolute bottom-6 text-sm text-slate-300">Sign out</button></aside><main className="content min-h-screen md:ml-64"><header className="flex items-center justify-between border-b bg-white px-5 py-4 md:px-10"><span className="font-semibold">{path?.replace("/", " ")}</span><span className="text-sm text-slate-500">Protected workspace</span></header><div className="mx-auto max-w-7xl p-5 md:p-10">{children}</div></main></div>;
}

