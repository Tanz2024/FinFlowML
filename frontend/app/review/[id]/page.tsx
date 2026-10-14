"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Shell from "../../../components/Shell";
import { api, Review } from "../../../lib/api";
import { dirtyCorrections, REVIEW_FIELDS, ReviewField } from "../../../lib/review";

const labels: Record<ReviewField, string> = { company: "Company", receipt_date: "Receipt date", address: "Address", total: "Total", currency: "Currency" };

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Review | null>(null);
  const [values, setValues] = useState<Record<ReviewField, string>>({ company: "", receipt_date: "", address: "", total: "", currency: "" });
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [role, setRole] = useState(""); const [loading, setLoading] = useState(true);
  const canReview = role === "admin" || role === "reviewer";
  async function load() {
    try { setLoading(true); const d = await api<Review>(`/receipts/${id}/review`); setData(d); setValues(Object.fromEntries(REVIEW_FIELDS.map((f) => [f, d.fields[f]?.reviewer_corrected_value ?? d.fields[f]?.effective_value ?? ""])) as Record<ReviewField, string>); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load review"); } finally { setLoading(false); }
  }
  useEffect(() => { fetch("/api/auth/me").then((r) => r.ok ? r.json() : Promise.reject()).then((me) => setRole(me.role)).catch(() => setRole("")); void load(); }, [id]);
  if (loading) return <Shell><p>Loading review…</p></Shell>;
  if (!data) return <Shell><p className="text-red-700">{error || "Review unavailable"}</p></Shell>;
  const original = Object.fromEntries(REVIEW_FIELDS.map((f) => [f, data.fields[f]?.reviewer_corrected_value ?? data.fields[f]?.effective_value ?? ""])) as Record<ReviewField, string>;
  const corrections = dirtyCorrections(original, values); const dirty = Object.keys(corrections).length > 0; const blocked = REVIEW_FIELDS.some((f) => data.fields[f].errors.length > 0);
  const onChange = (field: ReviewField, value: string) => setValues((current) => ({ ...current, [field]: value }));
  async function save() { try { await api(`/receipts/${id}/corrections`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ corrections }) }); setMessage("Corrections saved"); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Save failed"); } }
  async function action(kind: "approve" | "reject") { if (!confirm(kind === "approve" ? "Approve and create this expense?" : "Reject this receipt?")) return; try { await api(`/receipts/${id}/${kind}`, { method: "POST" }); setMessage(kind === "approve" ? "Approved and expense created" : "Receipt rejected"); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); } }
  return <Shell><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="label">Receipt review</p><h1 className="mt-2 text-3xl font-bold">Review extraction</h1><p className="mt-2 text-slate-500">Original predictions remain preserved for audit.</p></div><span className="pill bg-slate-100">{data.status}</span></div><div className="grid-responsive mt-8 grid grid-cols-2 gap-6"><div className="card"><img className="max-h-[520px] w-full rounded-lg object-contain" src={`/api/receipts/${id}/image`} alt="Receipt" /><p className="mt-3 text-xs text-slate-500">Protected receipt image</p></div><div className="card space-y-5">{REVIEW_FIELDS.map((f) => <div key={f}><div className="flex items-center justify-between"><label className="font-bold" htmlFor={f}>{labels[f]}</label><span className={`pill ${data.fields[f].status === "invalid" ? "bg-red-100 text-red-700" : "bg-slate-100"}`}>{data.fields[f].status}</span></div><p className="mt-1 text-xs text-slate-500">Original: {data.fields[f].original_model_value ?? "—"} · Normalized: {data.fields[f].normalized_value ?? "—"}</p><input id={f} className="input mt-2" value={values[f]} onChange={(e) => onChange(f, e.target.value)} disabled={!canReview} />{data.fields[f].errors.map((err) => <p className="mt-1 text-sm text-red-700" key={err}>{err}</p>)}</div>)}{dirty && <p className="text-amber-700">Save corrections before approving.</p>}{!canReview && <p className="text-slate-600">Your role can view this receipt but cannot edit or approve it.</p>}{error && <p className="text-red-700">{error}</p>}{message && <p className="text-green-700">{message}</p>}{canReview && <div className="flex flex-wrap gap-3"><button className="btn btn-secondary" disabled={!dirty} onClick={save}>Save corrections</button><button className="btn btn-primary" disabled={dirty || blocked || data.status !== "needs_review"} onClick={() => action("approve")}>Approve expense</button><button className="btn btn-danger" disabled={dirty || data.status !== "needs_review"} onClick={() => action("reject")}>Reject</button></div>}</div></div></Shell>;
}

