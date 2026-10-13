from enum import StrEnum


class ReceiptStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


VALID_TRANSITIONS = {
    ReceiptStatus.PENDING: {ReceiptStatus.PROCESSING, ReceiptStatus.REJECTED},
    ReceiptStatus.PROCESSING: {ReceiptStatus.NEEDS_REVIEW, ReceiptStatus.FAILED},
    ReceiptStatus.NEEDS_REVIEW: {ReceiptStatus.APPROVED, ReceiptStatus.REJECTED},
    ReceiptStatus.FAILED: {ReceiptStatus.PROCESSING, ReceiptStatus.REJECTED},
    ReceiptStatus.APPROVED: set(),
    ReceiptStatus.REJECTED: set(),
}
