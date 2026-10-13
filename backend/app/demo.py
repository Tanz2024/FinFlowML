"""Small isolated web demo for the Stage 5 receipt pipeline."""

import os
from email.parser import BytesParser
from email.policy import default

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.core.auth import CurrentUser, require_permission
from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.models.receipt import Receipt
from backend.app.services.extraction_jobs import create_job, durable_upload

router = APIRouter()

DEMO_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>FinFlowML Receipt Demo</title>
<style>body{font:16px system-ui;max-width:720px;margin:40px auto;padding:0 20px}
img{max-width:100%;max-height:360px;display:block;margin:16px 0}button{padding:10px 16px}
pre{background:#f4f4f4;padding:12px;white-space:pre-wrap}.error{color:#b00020}</style></head>
<body><h1>FinFlowML Receipt Review</h1><p><strong>Local demo:</strong> approval creates an expense only after review. Mock mode is labeled and is not AI inference.</p>
<input id="image" type="file" accept="image/*"><img id="preview" hidden>
<button id="extract" disabled>Extract Receipt Data</button><p id="status"></p>
<div id="review" hidden><label>Company <input id="company"></label><label>Date <input id="date" type="date"></label><label>Address <input id="address"></label><label>Total <input id="total"></label><label>Currency <input id="currency" value="USD"></label><button id="approve">Approve and create expense</button><button id="reject">Reject</button></div><pre id="result" hidden></pre>
<script>
const image=document.querySelector('#image'), preview=document.querySelector('#preview');
const button=document.querySelector('#extract'), status=document.querySelector('#status'), review=document.querySelector('#review'); let receiptId;
const result=document.querySelector('#result');
image.onchange=()=>{const file=image.files[0]; button.disabled=!file; if(file){preview.src=URL.createObjectURL(file);preview.hidden=false}};
button.onclick=async()=>{const data=new FormData();data.append('receipt',image.files[0]);button.disabled=true;status.textContent='Extracting…';result.hidden=true;
try{const response=await fetch('/predict',{method:'POST',headers:{'Authorization':'Bearer '+localStorage.getItem('finflow_token'),'Idempotency-Key':crypto.randomUUID()},body:data});const body=await response.json();if(!response.ok)throw new Error(body.detail||'Upload failed'); receiptId=body.receipt_id; status.textContent='Queued: '+body.job_id+'. Waiting for extraction…'; poll(body.job_id); result.textContent=JSON.stringify(body,null,2);result.hidden=false;}
catch(error){status.textContent=error.message;status.className='error';}finally{button.disabled=false;}};
async function poll(job){const response=await fetch('/jobs/'+job,{headers:{'Authorization':'Bearer '+localStorage.getItem('finflow_token')}});const body=await response.json();status.textContent='Job status: '+body.state;if(body.state==='completed'){const receipt=await fetch('/receipts/'+body.receipt_id,{headers:{'Authorization':'Bearer '+localStorage.getItem('finflow_token')}});const data=await receipt.json();for(const field of ['company','receipt_date','address','total','currency'])document.querySelector('#'+(field==='receipt_date'?'date':field)).value=data[field]||'';review.hidden=false;return;}if(['terminal_failed'].includes(body.state)){status.textContent='Extraction failed: '+(body.error_message||'unknown error');return;}setTimeout(()=>poll(job),2000);}
document.querySelector('#approve').onclick=async()=>{const corrections={company:company.value,date:date.value,address:address.value,total:total.value,currency:currency.value};const response=await fetch('/receipts/'+receiptId+'/corrections',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({corrections})});if(!response.ok){status.textContent='Correction failed';return;}const approved=await fetch('/receipts/'+receiptId+'/approve',{method:'POST'});status.textContent=approved.ok?'Approved; expense created.':'Approval failed: '+(await approved.text());};
document.querySelector('#reject').onclick=async()=>{const response=await fetch('/receipts/'+receiptId+'/reject',{method:'POST'});status.textContent=response.ok?'Receipt rejected.':'Rejection failed';};
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


@router.post("/predict", status_code=202)
async def predict_receipt(request: Request, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("review")), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(status_code=415, detail="Upload an image as multipart form data")
    filename, payload = _uploaded_file(await request.body(), content_type)
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    path = durable_upload(actor.organization_id, filename, payload)
    item = Receipt(
        organization_id=actor.organization_id,
        source_filename=filename,
        ocr_text="mock OCR text" if os.environ.get("FINFLOW_MOCK_EXTRACTION") else None,
        status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    job = create_job(db, actor.organization_id, item, path, idempotency_key)
    return {"job_id": str(job.id), "receipt_id": str(item.id), "state": job.state, "mock": bool(os.environ.get("FINFLOW_MOCK_EXTRACTION"))}
