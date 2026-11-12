from .agents.finance import FinanceAgent
from .agents.recommendation import RecommendationAgent
from .agents.research import ResearchAgent
from .agents.risk import RiskAgent
from .models import AgentExecution, FindingSeverity, PendingApproval, Product, PurchaseRequest, RecommendationSelection, WorkflowResponse
from .repository import MemoryRepository


class Orchestrator:
    """Coordinates agents. Only policy-eligible workflows become pending approvals."""
    def __init__(self, repo: MemoryRepository, research: ResearchAgent, finance: FinanceAgent, risk: RiskAgent, recommendation: RecommendationAgent) -> None:
        self.repo, self.research, self.finance, self.risk, self.recommendation = repo, research, finance, risk, recommendation

    async def process(self, request: PurchaseRequest) -> WorkflowResponse:
        await self.repo.save_request(request)
        research = await self.research.execute(request)
        finance = await self.finance.execute(request, research.products)
        risk = await self.risk.execute(request, research.products)
        if finance.status == FindingSeverity.fail or risk.status == FindingSeverity.fail:
            await self.repo.log(AgentExecution(request_id=request.id, agent="orchestrator", status="blocked", output={"reason":"finance_or_risk_policy"}))
            return WorkflowResponse(request_id=request.id, status="blocked", research=research, finance=finance, risk=risk, executions=[entry for entry in self.repo.executions if entry.request_id == request.id])
        recommendation = await self.recommendation.execute(request, research.products, finance, risk)
        if recommendation.status == FindingSeverity.fail or not recommendation.selected_product_id:
            return WorkflowResponse(request_id=request.id, status="blocked", research=research, finance=finance, risk=risk, recommendation=recommendation, executions=[entry for entry in self.repo.executions if entry.request_id == request.id])
        await self.repo.save_workflow(str(request.id), {"request":request, "research":research, "finance":finance, "risk":risk, "recommendation":recommendation})
        return WorkflowResponse(request_id=request.id, status="recommendation_ready", research=research, finance=finance, risk=risk, recommendation=recommendation, executions=[entry for entry in self.repo.executions if entry.request_id == request.id])

    async def select_recommendation(self, request_id: str, selection: RecommendationSelection, user_id: str) -> PendingApproval:
        workflow = await self.repo.get_workflow(request_id)
        if not workflow: raise LookupError("Purchase workflow is not available")
        if workflow["request"].user_id != user_id: raise PermissionError("Purchase request does not belong to current user")
        recommendation = workflow["recommendation"]
        permitted = {item.product_id for item in recommendation.ranked}
        if selection.product_id not in permitted: raise PermissionError("Selected product is not an eligible recommendation")
        product = next((item for item in workflow["research"].products if item.id == selection.product_id), None)
        if not product: raise PermissionError("Selected product is not in the server catalog result")
        request = workflow["request"]
        approval = PendingApproval(purchase_request_id=request.id, user_id=request.user_id, product_id=product.id, amount_minor=product.price_minor, currency=product.currency)
        await self.repo.save_approval(approval)
        return approval
