"""Invoice creation service, including line-item persistence."""

from sqlalchemy.orm import Session

from backend.app.models.invoice import Invoice
from backend.app.models.invoice_item import InvoiceItem
from backend.app.schemas.invoice import InvoiceCreate


def create_invoice(db: Session, payload: InvoiceCreate, organization_id=None) -> Invoice:
    data = payload.model_dump(exclude={"items"})
    invoice = Invoice(organization_id=organization_id, **data)
    db.add(invoice)
    db.flush()
    for item in payload.items:
        db.add(InvoiceItem(invoice_id=invoice.id, **item.model_dump()))
    db.commit()
    db.refresh(invoice)
    return invoice
