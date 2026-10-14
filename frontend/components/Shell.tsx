"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const links = [{ href: "/dashboard", label: "Dashboard" }, { href: "/expenses", label: "Expenses" }, { href: "/invoices", label: "Invoices" }, { href: "/customers", label: "Customers" }, { href: "/payments", label: "Payments" }, { href: "/pending", label: "Pending reviews" }];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname(); const router = useRouter(); const [role, setRole] = useState(""); const [open, setOpen] = useState(false);
  useEffect(() => { fetch("/api/auth/me").then((r) => r.ok ? r.json() : Promise.reject()).then((me) => setRole(me.role)).catch(() => router.push("/login")); }, [router]);
  async function logout() { try { const response = await fetch("/api/auth/logout", { method: "POST", headers: { "content-type": "application/json" }, cache: "no-store" }); if (!response.ok) throw new Error("Logout failed"); setRole(""); router.replace("/login"); } catch { router.replace("/login?error=logout"); } }
  const canScan = role === "admin" || role === "reviewer"; const canAccounting = role === "admin" || role === "accountant";
  const visible = links.filter((link) => link.href !== "/expenses" || true).filter((link) => link.href !== "/invoices" || canAccounting || role === "viewer").filter((link) => link.href !== "/customers" || canAccounting || role === "viewer").filter((link) => link.href !== "/payments" || canAccounting || role === "viewer");
  const nav = <nav className="space-y-1">{visible.map((link) => <Link key={link.href} onClick={() => setOpen(false)} className={path === link.href ? "active" : ""} href={link.href}>{link.label}</Link>)}{canScan && <Link onClick={() => setOpen(false)} className={path === "/scan" ? "active" : ""} href="/scan">Scan receipt</Link>}</nav>;
  return <div className="min-h-screen"><aside className="sidebar fixed inset-y-0 left-0 hidden w-64 p-6 md:block"><p className="text-xl font-bold text-white">FinFlow<span className="text-blue-300">ML</span></p><p className="mt-1 text-xs text-slate-400">Finance operations</p><div className="mt-10">{nav}</div><button onClick={logout} className="absolute bottom-6 text-sm text-slate-300">Sign out</button></aside>{open && <button aria-label="Close navigation" className="fixed inset-0 z-20 bg-slate-950/40 md:hidden" onClick={() => setOpen(false)} /> }<main className="content min-h-screen md:ml-64"><header className="flex items-center justify-between border-b bg-white px-5 py-4 md:px-10"><button aria-label="Open navigation" aria-expanded={open} className="rounded p-2 text-xl md:hidden" onClick={() => setOpen(true)}>☰</button><span className="font-semibold">{path?.replace("/", " ")}</span><span className="text-sm text-slate-500">Protected workspace</span></header>{open && <aside className="sidebar fixed inset-y-0 left-0 z-30 w-72 p-6 md:hidden"><p className="text-xl font-bold text-white">FinFlow<span className="text-blue-300">ML</span></p><div className="mt-10">{nav}</div><button onClick={logout} className="absolute bottom-6 text-sm text-slate-300">Sign out</button></aside>}<div className="mx-auto max-w-7xl p-5 md:p-10">{children}</div></main></div>;
}

