from ..models import FindingSeverity, FinanceResult, Product, PurchaseRequest
from .base import BaseAgent


class FinanceAgent(BaseAgent):
    name = "finance"
    async def run(self, request: PurchaseRequest, products: list[Product]) -> FinanceResult:
        if not products:
            return FinanceResult(status=FindingSeverity.fail, total_minor=0, budget_remaining_minor=request.budget_minor, recurring_cost_minor=0, violations=["No eligible products found"])
        total = min(p.price_minor for p in products)
        chosen = next(p for p in products if p.price_minor == total)
        violations: list[str] = []
        if total > request.budget_minor: violations.append("Selected product exceeds configured budget")
        if total > request.max_transaction_minor: violations.append("Selected product exceeds maximum transaction limit")
        status = FindingSeverity.fail if violations else FindingSeverity.pass_
        return FinanceResult(status=status, total_minor=total, budget_remaining_minor=request.budget_minor-total, recurring_cost_minor=chosen.recurring_cost_minor, violations=violations)
