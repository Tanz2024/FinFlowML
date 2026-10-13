"""AI finance assistant foundation.

This module defines typed retrieval and context-building interfaces that a future
LLM-backed assistant will use to answer questions like "how much did I spend on
food?" or "what is my monthly profit?". It does not call an LLM: retrieval is
grounded in existing accounting/expense services, and callers get a typed context
object with citations to the underlying records, not free-text answers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.expense import Expense
from backend.app.models.expense_category import ExpenseCategory
from backend.app.services import accounting as accounting_service


@dataclass
class FinancialFact:
    """A single retrieved, source-attributed fact for grounding an assistant answer."""

    label: str
    value: Decimal | str
    source: str


@dataclass
class FinancialContext:
    """The typed bundle of facts a retrieval query produces, ready for a future LLM prompt."""

    query: str
    facts: list[FinancialFact] = field(default_factory=list)


class FinancialRetriever(ABC):
    """Contract for retrieving grounded financial facts. No table access outside this layer."""

    @abstractmethod
    def retrieve(self, db: Session, query: str) -> list[FinancialFact]:
        raise NotImplementedError


class CategorySpendingRetriever(FinancialRetriever):
    """Answers "how much did I spend on <category>?" style queries."""

    def retrieve(self, db: Session, query: str) -> list[FinancialFact]:
        lowered = query.lower()
        categories = db.scalars(select(ExpenseCategory)).all()
        matched = [c for c in categories if c.name.lower() in lowered]
        facts: list[FinancialFact] = []
        for category in matched:
            total = sum(
                (e.amount for e in db.scalars(
                    select(Expense).where(Expense.category_id == category.id)
                ).all()),
                start=Decimal("0"),
            )
            facts.append(
                FinancialFact(
                    label=f"spending_on_{category.name}",
                    value=total,
                    source="expenses.category_id",
                )
            )
        return facts


class ProfitRetriever(FinancialRetriever):
    """Answers "what is my monthly profit?" / "why did expenses increase?" style queries."""

    def retrieve(self, db: Session, query: str) -> list[FinancialFact]:
        summary = accounting_service.get_summary(db)
        return [
            FinancialFact(label="total_revenue", value=summary.total_revenue, source="payments"),
            FinancialFact(label="total_expenses", value=summary.total_expenses, source="expenses"),
            FinancialFact(label="net_profit", value=summary.net_profit, source="derived"),
        ]


DEFAULT_RETRIEVERS: list[FinancialRetriever] = [CategorySpendingRetriever(), ProfitRetriever()]


def build_context(
    db: Session, query: str, retrievers: list[FinancialRetriever] | None = None
) -> FinancialContext:
    """Run retrievers against the query and assemble a typed, citable context.

    This is the seam where a future LLM assistant will attach: it consumes a
    FinancialContext instead of touching the database directly.
    """
    facts: list[FinancialFact] = []
    for retriever in retrievers or DEFAULT_RETRIEVERS:
        facts.extend(retriever.retrieve(db, query))
    return FinancialContext(query=query, facts=facts)
