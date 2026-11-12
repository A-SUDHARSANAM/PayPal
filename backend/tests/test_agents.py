import pytest
from app.agents.finance import FinanceAgent
from app.agents.payment import PaymentAgent
from app.agents.recommendation import RecommendationAgent
from app.agents.research import ResearchAgent
from app.agents.risk import RiskAgent
from app.catalog import CATALOG
from app.config import Settings
from app.models import ApprovalStatus, FindingSeverity, PendingApproval, ProductRequirement, PurchaseRequest, RecommendationSelection
from app.orchestrator import Orchestrator
from app.repository import MemoryRepository


class MockGemini:
    async def generate(self, prompt, schema):
        assert schema is ProductRequirement
        return ProductRequirement(category="headphones", keywords=["headphones"], desired_features=["noise cancellation"], max_price_minor=40000)


def request(text="Need noise cancelling headphones", budget=40000, limit=50000):
    return PurchaseRequest(user_id="user-1", text=text, budget_minor=budget, max_transaction_minor=limit)


@pytest.mark.asyncio
async def test_research_uses_mocked_gemini_but_returns_server_catalog_products():
    repo = MemoryRepository()
    result = await ResearchAgent(repo, gemini=MockGemini()).execute(request())
    assert result.requirements.category == "headphones"
    assert result.products and all(p.is_demo for p in result.products)
    assert all(p.category == "headphones" for p in result.products)


@pytest.mark.asyncio
async def test_finance_blocks_maximum_transaction_limit():
    repo = MemoryRepository()
    result = await FinanceAgent(repo).execute(request(limit=10000), [CATALOG[0]])
    assert result.status == FindingSeverity.fail
    assert "maximum transaction" in result.violations[0]


@pytest.mark.asyncio
async def test_risk_detects_duplicate_request():
    repo = MemoryRepository(); prior = request(); await repo.save_request(prior)
    result = await RiskAgent(repo).execute(request(), [CATALOG[0]])
    assert result.duplicate_detected is True
    assert result.status == FindingSeverity.fail


@pytest.mark.asyncio
async def test_recommendation_ranks_only_eligible_inputs():
    repo = MemoryRepository(); req = request()
    finance = await FinanceAgent(repo).execute(req, [CATALOG[0], CATALOG[1]])
    risk = await RiskAgent(repo).execute(req, [CATALOG[0], CATALOG[1]])
    result = await RecommendationAgent(repo).execute(req, [CATALOG[0], CATALOG[1]], finance, risk)
    assert result.status == FindingSeverity.pass_
    assert result.selected_product_id in {CATALOG[0].id, CATALOG[1].id}


@pytest.mark.asyncio
async def test_orchestrator_creates_pending_approval_only_after_explicit_selection():
    repo = MemoryRepository()
    flow = Orchestrator(repo, ResearchAgent(repo, gemini=MockGemini()), FinanceAgent(repo), RiskAgent(repo), RecommendationAgent(repo))
    output = await flow.process(request())
    assert output.status == "recommendation_ready"
    assert output.approval is None
    approval = await flow.select_recommendation(str(output.request_id), RecommendationSelection(product_id="demo-headphones-2"), "user-1")
    assert approval.status == ApprovalStatus.pending
    assert approval.amount_minor == 29900


@pytest.mark.asyncio
async def test_payment_refuses_pending_or_price_tampered_approval():
    payment = PaymentAgent(Settings(paypal_base_url="https://api-m.sandbox.paypal.com"), MemoryRepository())
    pending = PendingApproval(purchase_request_id=request().id, user_id="user-1", product_id=CATALOG[0].id, amount_minor=1, currency="USD")
    with pytest.raises(PermissionError): await payment.create_order(pending, CATALOG[0])
    pending.status = ApprovalStatus.approved
    with pytest.raises(PermissionError): await payment.create_order(pending, CATALOG[0])
