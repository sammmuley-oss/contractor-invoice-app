"""Pydantic schemas for bank statements and transactions."""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


# ─── Bank Statement ───────────────────────────────────────

class BankStatementResponse(BaseModel):
    """Response schema for a bank statement."""
    statement_id: int
    bank_name: str
    file_name: str
    upload_date: datetime
    statement_start_date: Optional[date] = None
    statement_end_date: Optional[date] = None
    total_transactions: int = 0
    created_date: datetime

    model_config = {"from_attributes": True}


# ─── Bank Transaction ─────────────────────────────────────

class BankTransactionResponse(BaseModel):
    """Response schema for a bank transaction."""
    transaction_id: int
    statement_id: int
    transaction_date: Optional[date] = None
    description: Optional[str] = None
    credit_amount: float = 0
    debit_amount: float = 0
    utr_number: Optional[str] = None
    reference_number: Optional[str] = None
    sender_name: Optional[str] = None
    match_status: str = "Unmatched"
    matched_invoice_number: Optional[str] = None
    confidence_score: Optional[float] = None
    created_date: datetime

    # Joined fields (populated at API level)
    company_name: Optional[str] = None
    invoice_amount: Optional[float] = None
    bank_name: Optional[str] = None

    model_config = {"from_attributes": True}


class BankStatementDetailResponse(BaseModel):
    """Statement with its transactions."""
    statement: BankStatementResponse
    transactions: list[BankTransactionResponse] = []


# ─── Reconciliation Actions ───────────────────────────────

class ManualMatchRequest(BaseModel):
    """Request body for manually matching a transaction to an invoice."""
    transaction_id: int
    invoice_number: str


class ReconciliationSummary(BaseModel):
    """Summary counts for the reconciliation dashboard."""
    total_transactions: int = 0
    matched: int = 0
    needs_review: int = 0
    unmatched: int = 0
    rejected: int = 0
    total_matched_amount: float = 0
    total_unmatched_amount: float = 0
