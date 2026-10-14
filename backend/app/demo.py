"""Small isolated web demo for the Stage 5 receipt pipeline."""

import hashlib
import os
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.auth import CurrentUser, require_permission
from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.models.extraction_job import ExtractionJob
from backend.app.models.receipt import Receipt
from backend.app.services.audit import record_event
from backend.app.services.extraction_jobs import create_job, durable_upload

router = APIRouter()

DEMO_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>FinFlowML Receipt Demo</title>
<style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 20px;color:#17202a}button{padding:10px 14px;margin:4px;border:0;border-radius:6px;background:#155eef;color:#fff}button.secondary{background:#59636e}button.danger{background:#b42318}button:disabled{opacity:.5}input,textarea{padding:8px;width:100%;box-sizing:border-box;margin:4px 0 12px}img{max-width:100%;max-height:420px;display:block;border-radius:8px}.grid{display:grid;grid-template-columns:minmax(260px,1fr) minmax(360px,1.4fr);gap:24px}.card{border:1px solid #d0d5dd;border-radius:10px;padding:16px;margin:16px 0}.field{display:grid;grid-template-columns:130px 1fr;gap:8px;align-items:start;border-top:1px solid #eaecf0;padding:12px 0}.field small{display:block;color:#667085}.state{font-weight:600}.valid{color:#067647}.invalid{color:#b42318}.corrected{color:#175cd3}.missing{color:#667085}.error{color:#b42318}.sr{position:absolute;left:-10000px}</style></head>
<body><h1>FinFlowML Receipt Review</h1><p><strong>Human review required:</strong> saving corrections never approves or posts an expense. Mock extraction mode is clearly labeled and is not AI inference.</p>
<section id="login" class="card"><label>Email<input id="email" type="email" autocomplete="username"></label><label>Password<input id="password" type="password" autocomplete="current-password"></label><label>Organization ID (optional)<input id="organization"></label><button id="loginButton">Log in</button><p id="loginStatus" role="status"></p></section>
<section id="app" hidden><div class="card"><label>Open receipt by ID<input id="receiptIdInput" placeholder="Receipt ID"></label><button id="openReceipt" class="secondary">Open receipt</button><label>Pending receipts<select id="pending"><option value="">Select a receipt…</option></select></label></div><div class="grid"><div><div class="card"><label>Receipt image<input id="image" type="file" accept="image/*"></label><img id="preview" alt="Uploaded receipt preview" hidden><button id="extract" disabled>Extract Receipt Data</button><p id="mode"></p><p id="status" role="status" aria-live="polite"></p><button id="retry" class="secondary" hidden>Retry extraction</button></div></div><div><div id="review" class="card" hidden><h2>Review extracted fields</h2><div id="fields"></div><p id="unsaved" class="error" hidden>Save corrections before approving.</p><button id="save">Save Corrections</button><button id="approve" disabled>Approve and create expense</button><button id="reject" class="danger">Reject</button><p id="message" role="status"></p></div></div></div></section>
<script>
let token=null,role=null,receiptId=null,jobId=null,pollGeneration=0,reviewData=null,initialValues={},dirty=new Set(),imageUrl=null;const fields=['company','receipt_date','address','total','currency'];const labels={company:'Company',receipt_date:'Receipt date',address:'Address',total:'Total',currency:'Currency'};const $=id=>document.getElementById(id);const esc=v=>v==null?'(none)':String(v);
function showMessage(text,error=false){$('message').textContent=text;$('message').className=error?'error':''}function auth(){return {'Authorization':'Bearer '+token}}function canReview(){return role==='admin'||role==='reviewer'}function canApprove(){return canReview()}function apiError(r,data){if(r.status===401){token=null;$('app').hidden=true;$('login').hidden=false;throw new Error('Session expired; please log in again.')}throw new Error(data?.detail||'Request failed')}
function updateActions(blocked){const unsaved=dirty.size>0;$('unsaved').hidden=!unsaved;$('save').disabled=!canReview()||!unsaved;$('approve').disabled=!canApprove()||blocked||unsaved||reviewData.status!=='needs_review';$('reject').disabled=!canApprove()}
function renderReview(data){reviewData=data;dirty.clear();const container=$('fields');container.replaceChildren();let blocked=false;for(const field of fields){const item=data.fields[field];const row=document.createElement('div');row.className='field';const title=document.createElement('strong');title.textContent=labels[field];const body=document.createElement('div');const state=document.createElement('span');state.className='state '+item.status;state.textContent=item.status;body.append(state);for(const [name,key] of [['Original model','original_model_value'],['Normalized','normalized_value'],['Reviewer correction','reviewer_corrected_value'],['Effective','effective_value']]){const line=document.createElement('small');line.textContent=name+': '+esc(item[key]);body.append(line)}if(item.errors.length){blocked=true;const errors=document.createElement('small');errors.className='error';errors.textContent='Errors: '+item.errors.join('; ');body.append(errors)}const input=document.createElement(field==='address'?'textarea':'input');input.name=field;input.value=item.reviewer_corrected_value??item.effective_value??'';initialValues[field]=input.value;input.setAttribute('aria-label','Correction for '+labels[field]);input.oninput=()=>{if(input.value!==initialValues[field])dirty.add(field);else dirty.delete(field);updateActions(blocked)};body.append(input);row.append(title,body);container.append(row)}$('review').hidden=false;$('save').hidden=!canReview();$('reject').hidden=!canApprove();updateActions(blocked)}
async function loadReview(){const r=await fetch('/receipts/'+receiptId+'/review',{headers:auth()});const data=await r.json();if(!r.ok)apiError(r,data);renderReview(data);await loadImage()}
async function loadImage(){if(imageUrl)URL.revokeObjectURL(imageUrl);const r=await fetch('/receipts/'+receiptId+'/image',{headers:auth()});if(!r.ok){$('preview').hidden=true;return}imageUrl=URL.createObjectURL(await r.blob());$('preview').src=imageUrl;$('preview').hidden=false}
async function poll(generation=pollGeneration){if(generation!==pollGeneration)return;try{const r=await fetch('/jobs/'+jobId,{headers:auth()});const data=await r.json();if(!r.ok)apiError(r,data);if(generation!==pollGeneration)return;$('status').textContent='Job status: '+data.state;if(data.state==='completed'){await loadReview();return}if(['terminal_failed','retryable_failed'].includes(data.state)){ $('status').textContent='Extraction failed: '+(data.error_message||data.state);$('retry').hidden=data.state!=='retryable_failed';return}setTimeout(()=>poll(generation),1500)}catch(e){if(generation===pollGeneration){$('status').textContent=e.message;$('status').className='error'}}}
$('image').onchange=()=>{const file=$('image').files[0];$('extract').disabled=!file;if(file){$('preview').src=URL.createObjectURL(file);$('preview').hidden=false}};
$('extract').onclick=async()=>{pollGeneration++;const generation=pollGeneration;const form=new FormData();form.append('receipt',$('image').files[0]);$('extract').disabled=true;$('status').textContent='Uploading…';try{const r=await fetch('/predict',{method:'POST',headers:{...auth(),'Idempotency-Key':crypto.randomUUID()},body:form});const data=await r.json();if(!r.ok)apiError(r,data);receiptId=data.receipt_id;jobId=data.job_id;$('mode').textContent=data.mock?'MOCK EXTRACTION — not AI inference':'Live extraction';$('status').textContent='Queued; waiting for extraction…';poll(generation)}catch(e){showMessage(e.message,true)}finally{$('extract').disabled=false}};
$('retry').onclick=async()=>{const r=await fetch('/jobs/'+jobId+'/retry',{method:'POST',headers:auth()});if(!r.ok){showMessage('Retry failed',true);return}$('retry').hidden=true;$('status').textContent='Retry queued…';poll()};
function corrections(){const out={};for(const field of fields){const input=document.querySelector('[name="'+field+'"]');out[field]=input.value||null}return out}
$('save').onclick=async()=>{try{const all=corrections(),changed={};for(const field of dirty)changed[field]=all[field];const r=await fetch('/receipts/'+receiptId+'/corrections',{method:'PATCH',headers:{...auth(),'Content-Type':'application/json'},body:JSON.stringify({corrections:changed})});const data=await r.json();if(!r.ok)apiError(r,data);await loadReview();showMessage('Corrections saved. Approval remains a separate action.')}catch(e){showMessage(e.message,true)}};
$('approve').onclick=async()=>{if(!confirm('Approve this reviewed receipt and create an expense?'))return;try{const r=await fetch('/receipts/'+receiptId+'/approve',{method:'POST',headers:auth()});const data=await r.json();if(!r.ok)throw new Error(data.detail||'Approval failed');showMessage('Approved; expense created.');$('approve').disabled=true;$('save').disabled=true;$('reject').disabled=true}catch(e){showMessage(e.message,true);await loadReview()}};
$('reject').onclick=async()=>{if(!confirm('Reject this receipt?'))return;try{const r=await fetch('/receipts/'+receiptId+'/reject',{method:'POST',headers:auth()});if(!r.ok)throw new Error((await r.json()).detail||'Rejection failed');showMessage('Receipt rejected.');$('approve').disabled=true;$('save').disabled=true;$('reject').disabled=true}catch(e){showMessage(e.message,true)}};
$('openReceipt').onclick=async()=>{pollGeneration++;receiptId=$('receiptIdInput').value.trim();if(!receiptId){showMessage('Enter a receipt ID',true);return}try{await loadReview();$('status').textContent='Receipt loaded.'}catch(e){showMessage(e.message,true)}};
$('pending').onchange=async()=>{if(!$('pending').value)return;pollGeneration++;receiptId=$('pending').value;try{await loadReview()}catch(e){showMessage(e.message,true)}};
async function loadPending(){const r=await fetch('/receipts/pending',{headers:auth()});const data=await r.json();if(!r.ok)apiError(r,data);const select=$('pending');for(const item of data){const option=document.createElement('option');option.value=item.id;option.textContent=(item.company||item.id)+' — '+item.status;select.append(option)}}
$('loginButton').onclick=async()=>{const body={email:$('email').value,password:$('password').value};if($('organization').value)body.organization_id=$('organization').value;try{const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)apiError(r,data);token=data.access_token;role=data.role;$('login').hidden=true;$('app').hidden=false;$('loginStatus').textContent='Authenticated; token kept in memory only.';await loadPending()}catch(e){$('loginStatus').textContent=e.message;$('loginStatus').className='error'}};
</script></body></html>"""


def _uploaded_file(body: bytes, content_type: str) -> tuple[str, bytes]:
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
    )
    for part in message.iter_attachments():
        filename = part.get_filename() or "receipt.jpg"
        payload = part.get_payload(decode=True)
        if payload:
            if len(payload) > settings.max_upload_bytes:
                raise HTTPException(status_code=413, detail="uploaded file is too large")
            try:
                from io import BytesIO

                from PIL import Image
                with Image.open(BytesIO(payload)) as image:
                    image.verify()
            except Exception as exc:
                raise HTTPException(status_code=415, detail="uploaded file is not a valid image") from exc
            return filename, payload
    raise HTTPException(status_code=400, detail="Please upload a receipt image")


@router.get("/demo", response_class=HTMLResponse)
async def demo_page() -> str:
    return DEMO_HTML


@router.get("/receipts/{receipt_id}/image")
async def receipt_image(receipt_id: UUID, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    item = db.scalar(select(Receipt).where(Receipt.id == receipt_id, Receipt.organization_id == actor.organization_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    path = Path(item.image_reference or "")
    root = Path(settings.upload_root).resolve()
    try:
        safe_path = path.resolve(strict=True)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Receipt image not found") from None
    if root not in safe_path.parents or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="Receipt image not found")
    return FileResponse(safe_path)


@router.post("/predict", status_code=202)
async def predict_receipt(request: Request, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("review")), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), correlation_id: str | None = Header(default=None, alias="X-Correlation-ID")) -> dict[str, object]:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(status_code=415, detail="Upload an image as multipart form data")
    filename, payload = _uploaded_file(await request.body(), content_type)
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    payload_hash = hashlib.sha256(payload).hexdigest()
    existing = db.scalar(select(ExtractionJob).where(ExtractionJob.organization_id == actor.organization_id, ExtractionJob.idempotency_key == idempotency_key))
    if existing:
        if existing.payload_hash != payload_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used for different content")
        return {"job_id": str(existing.id), "receipt_id": str(existing.receipt_id), "state": existing.state, "mock": bool(os.environ.get("FINFLOW_MOCK_EXTRACTION"))}
    path = durable_upload(actor.organization_id, filename, payload)
    item = Receipt(
        organization_id=actor.organization_id,
        source_filename=filename,
        image_reference=path,
        ocr_text="mock OCR text" if os.environ.get("FINFLOW_MOCK_EXTRACTION") else None,
        status="pending",
    )
    db.add(item)
    db.flush()
    record_event(db, actor.organization_id, "receipt.uploaded", "receipt", item.id, actor_id=actor.user.id, correlation_id=correlation_id, details={"filename": filename, "payload_sha256": payload_hash})
    try:
        job = create_job(db, actor.organization_id, item, path, idempotency_key, payload_hash)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job_id": str(job.id), "receipt_id": str(item.id), "state": job.state, "mock": bool(os.environ.get("FINFLOW_MOCK_EXTRACTION"))}
