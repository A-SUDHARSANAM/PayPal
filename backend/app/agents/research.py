from ..catalog import CATALOG
from ..gemini import GeminiClient
from ..models import ProductRequirement, PurchaseRequest, ResearchResult
from .base import BaseAgent


class ResearchAgent(BaseAgent):
    name = "research"
    def __init__(self, *args: object, gemini: GeminiClient | None = None, **kwargs: object) -> None:
        super().__init__(*args, **kwargs); self.gemini = gemini

    async def run(self, request: PurchaseRequest, *args: object) -> ResearchResult:
        # Gemini extracts intent only. Catalog search and product data remain server-controlled.
        if self.gemini:
            requirements = await self.gemini.generate(f"Extract product requirements as JSON. Request: {request.text}", ProductRequirement)
        else:
            words = request.text.lower().replace("-", " ").split()
            category = next((p.category for p in CATALOG if p.category in words or any(p.category in w for w in words)), "")
            requirements = ProductRequirement(category=category or "general", keywords=words, max_price_minor=request.budget_minor)
        candidates = [p for p in CATALOG if p.eligible and (requirements.category == "general" or p.category == requirements.category)]
        candidates = [p for p in candidates if p.price_minor <= request.budget_minor][:5]
        comparisons = {p.id: f"{p.name}: {', '.join(p.features[:2])}; demo price is server catalog controlled." for p in candidates}
        return ResearchResult(requirements=requirements, products=candidates, comparisons=comparisons)
