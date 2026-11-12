from ..models import FindingSeverity, Product, PurchaseRequest, RiskResult
from ..repository import MemoryRepository
from .base import BaseAgent


class RiskAgent(BaseAgent):
    name = "risk"
    def __init__(self, repo: MemoryRepository, **kwargs: object) -> None: super().__init__(repo, **kwargs)
    async def run(self, request: PurchaseRequest, products: list[Product]) -> RiskResult:
        previous = await self.repo.recent_for_user(request.user_id)
        duplicate = any(p.id != request.id and p.text.strip().lower() == request.text.strip().lower() for p in previous)
        candidate = min(products, key=lambda x: x.price_minor) if products else None
        unusual = bool(candidate and candidate.price_minor > int(request.max_transaction_minor * .8))
        violations = []
        if not candidate: violations.append("No eligible catalog product")
        if candidate and not candidate.eligible: violations.append("Product is not eligible")
        if duplicate: violations.append("Duplicate purchase request detected")
        score = min(100, (50 if duplicate else 0) + (25 if unusual else 0) + (40 if violations else 0))
        status = FindingSeverity.fail if violations else (FindingSeverity.warning if unusual else FindingSeverity.pass_)
        explanation = "Duplicate or policy violation requires a human to create a new request." if violations else ("Amount is close to the configured limit." if unusual else "No duplicate, eligibility, or policy risk found.")
        return RiskResult(score=score, status=status, duplicate_detected=duplicate, unusual_amount=unusual, policy_violations=violations, explanation=explanation)
