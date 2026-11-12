from ..gemini import GeminiClient
from ..models import FindingSeverity, FinanceResult, Product, PurchaseRequest, RankedProduct, RecommendationResult, RiskResult
from .base import BaseAgent


class RecommendationAgent(BaseAgent):
    name = "recommendation"
    def __init__(self, *args: object, gemini: GeminiClient | None = None, **kwargs: object) -> None:
        super().__init__(*args, **kwargs); self.gemini = gemini
    async def run(self, request: PurchaseRequest, products: list[Product], finance: FinanceResult, risk: RiskResult) -> RecommendationResult:
        if finance.status == FindingSeverity.fail or risk.status == FindingSeverity.fail:
            return RecommendationResult(status=FindingSeverity.fail, ranked=[], explanation="Blocking finance or risk policy result.")
        eligible = sorted(products, key=lambda p: (p.price_minor, -len(p.features)))
        ranked = [RankedProduct(product_id=p.id, score=max(60, 95-i*7), reason=f"Within budget; {', '.join(p.features[:2])}") for i,p in enumerate(eligible)]
        return RecommendationResult(status=FindingSeverity.pass_, ranked=ranked, selected_product_id=ranked[0].product_id if ranked else None, explanation="Best eligible demo-catalog option based on server catalog price, requested features, finance, and risk results.")
