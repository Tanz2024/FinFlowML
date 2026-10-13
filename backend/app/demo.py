"""Small isolated web demo for the Stage 5 receipt pipeline."""

import os
import tempfile
from datetime import date
from decimal import Decimal
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.models.receipt import Receipt
from backend.app.services.receipt_review import store_extraction
from ml.inference.predict import predict_image

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
try{const response=await fetch('/predict',{method:'POST',body:data});const body=await response.json();if(!response.ok)throw new Error(body.detail||'Extraction failed'); receiptId=body.receipt_id; for(const field of ['company','date','address','total','currency']) document.querySelector('#'+field).value=body[field]||''; review.hidden=false; result.textContent=JSON.stringify(body,null,2);result.hidden=false;status.textContent='Review the extracted values before approval.';}
catch(error){status.textContent=error.message;status.className='error';}finally{button.disabled=false;}};
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
            return filename, payload
    raise HTTPException(status_code=400, detail="Please upload a receipt image")


@router.get("/demo", response_class=HTMLResponse)
async def demo_page() -> str:
    return DEMO_HTML


@router.post("/predict")
async def predict_receipt(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(status_code=415, detail="Upload an image as multipart form data")
    filename, payload = _uploaded_file(await request.body(), content_type)
    suffix = Path(filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix) as temporary:
        temporary.write(payload)
        temporary.flush()
        base_model = os.environ.get("FINFLOW_BASE_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
        adapter_path = os.environ.get(
            "ADAPTER_PATH",
            os.path.join(
                os.environ.get(
                    "FINFLOW_TRAINING_DIR", "/content/drive/MyDrive/FinFlowML-stage4-final-v2"
                ),
                "best_adapter",
            ),
        )
        try:
            if os.environ.get("FINFLOW_MOCK_EXTRACTION", "").lower() in {"1", "true", "yes"}:
                prediction = {"company": "Mock Cafe", "date": "2025-01-15", "address": "1 Demo Road", "total": "12.50", "currency": "USD"}
                parsing_error = None
            else:
                _, _, prediction, parsing_error = predict_image(temporary.name, base_model, adapter_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Receipt extraction failed: {exc}") from exc
    if prediction is None:
        raise HTTPException(status_code=422, detail=parsing_error or "Model output could not be parsed")
    item = Receipt(
        source_filename=filename,
        ocr_text="mock OCR text" if os.environ.get("FINFLOW_MOCK_EXTRACTION") else None,
        extracted_data=prediction,
        company=prediction.get("company"),
        receipt_date=date.fromisoformat(prediction["date"]) if prediction.get("date") else None,
        address=prediction.get("address"),
        total=Decimal(prediction["total"]) if prediction.get("total") else None,
        currency=prediction.get("currency", "USD"),
        status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    store_extraction(db, item)
    return {**prediction, "receipt_id": str(item.id), "status": item.status, "mock": bool(os.environ.get("FINFLOW_MOCK_EXTRACTION"))}
