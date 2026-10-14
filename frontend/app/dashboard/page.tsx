"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Shell from "../../components/Shell";
import { api, Summary } from "../../lib/api";

const money = (amount: string | number, currency: string) => new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(amount));
export default function Dashboard() {
  const [data, setData] = useState<Summary | null>(null); const [error, setError] = useState("");
  useEffect(() => { api<Summary>("/expenses/summary").then(setData).catch((e) => setError(e.message)); }, []);
  const currencies = Object.entries(data?.currency_totals ?? {}); const monthly = Object.entries(data?.monthly_totals ?? {}).map(([month, amount]) => ({ month, amount: Number(amount) }));
  return <Shell><p className="label">Overview</p><h1 className="mt-2 text-3xl font-bold">Financial dashboard</h1><p className="mt-2 text-slate-500">Approved expenses grouped by their original ISO currency.</p>{error && <p className="mt-6 text-red-700">{error}</p>}<div className="mt-8 grid gap-5 md:grid-cols-3"><div className="card"><p className="label">Currencies tracked</p><p className="mt-3 text-3xl font-bold">{currencies.length}</p></div><div className="card md:col-span-2"><p className="label">Currency totals</p><div className="mt-3 flex flex-wrap gap-4">{currencies.length ? currencies.map(([currency, amount]) => <span className="pill bg-blue-50 text-blue-800" key={currency}>{currency} {Number(amount).toFixed(2)}</span>) : <span className="text-slate-500">No approved expenses yet.</span>}</div></div></div><div className="card mt-6"><h2 className="font-bold">Monthly spending (native amounts)</h2>{monthly.length ? <ResponsiveContainer width="100%" height={280}><BarChart data={monthly}><XAxis dataKey="month" /><YAxis /><Tooltip /><Bar dataKey="amount" fill="#155eef" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer> : <p className="py-16 text-center text-slate-500">No approved expenses yet.</p>}</div></Shell>;
}
