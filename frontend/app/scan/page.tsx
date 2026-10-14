"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Shell from "../../components/Shell";
import { api } from "../../lib/api";

const allowed = ["image/jpeg", "image/png", "image/webp"];
function validate(file: File) { if (!allowed.includes(file.type)) return "Use a JPEG, PNG or WebP image."; if (file.size > 10 * 1024 * 1024) return "Receipt images must be 10 MB or smaller."; return ""; }

export default function Scan() {
  const [file, setFile] = useState<File | null>(null); const [status, setStatus] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const router = useRouter();
  function choose(candidate?: File) { if (!candidate) return; const problem = validate(candidate); setError(problem); if (!problem) setFile(candidate); }
  async function upload() { if (!file) return; setBusy(true); setError(""); const form = new FormData(); form.append("receipt", file);
    try { const job = await api<{ job_id: string; receipt_id: string; mock: boolean }>("/predict", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: form }); setStatus(job.mock ? "Queued · mock extraction (not Qwen inference)" : "Queued · live AI extraction");
      for (let i = 0; i < 90; i++) { await new Promise((resolve) => setTimeout(resolve, 1000)); const state = await api<{ state: string; error_message?: string }>(`/jobs/${job.job_id}`); setStatus(`Extraction ${state.state}`); if (state.state === "completed") { router.push(`/review/${job.receipt_id}`); return; } if (["terminal_failed", "retryable_failed"].includes(state.state)) throw new Error(state.error_message || "Extraction failed"); }
      throw new Error("Extraction timed out");
    } catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); } finally { setBusy(false); }
  }
  return <Shell><div className="max-w-3xl"><p className="label">AI receipt scanner</p><h1 className="mt-2 text-3xl font-bold">Turn receipts into reviewable data</h1><p className="mt-2 text-slate-500">Upload a receipt. Every result remains subject to human approval.</p><div className="card mt-8"><label className="flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 p-8 text-center" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); choose(e.dataTransfer.files[0]); }}><input className="sr-only" type="file" accept={allowed.join(",")} onChange={(e) => choose(e.target.files?.[0])} /><span className="text-lg font-bold">{file ? file.name : "Drop a receipt here or browse"}</span><span className="mt-2 text-sm text-slate-500">PNG, JPEG or WebP · max 10 MB</span></label>{error && <p className="mt-4 text-red-700" role="alert">{error}</p>}{status && <p className="mt-4 text-blue-700" role="status">{status}</p>}<button className="btn btn-primary mt-5" disabled={!file || busy} onClick={upload}>{busy ? "Processing…" : "Start extraction"}</button></div></div></Shell>;
}

