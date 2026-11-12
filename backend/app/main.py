from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from .agents.finance import FinanceAgent
from .agents.recommendation import RecommendationAgent
from .agents.research import ResearchAgent
from .agents.risk import RiskAgent
from .catalog import CATALOG
from .config import settings
from .models import ApprovalDecision, ApprovalStatus, CreateOrderRequest, CreatePurchaseRequest, PayPalOrderView, PurchaseRequest, RecommendationSelection, WorkflowResponse
from .orchestrator import Orchestrator
from .repository import create_repository
from .agents.payment import PaymentAgent
from .security import CurrentUser, current_user
from .observability import RequestLoggingMiddleware, rate_limit

repo = create_repository(settings)
orchestrator = Orchestrator(repo, ResearchAgent(repo), FinanceAgent(repo), RiskAgent(repo), RecommendationAgent(repo))
payment_agent = PaymentAgent(settings, repo)

app = FastAPI(title="AgentPay API", version="0.1.0", description="Demo catalog and PayPal Sandbox only. LLMs never authorize payments.")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()], allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])
app.add_middleware(RequestLoggingMiddleware)

@app.get("/healthz")
async def health() -> dict[str, str]: return {"status":"ok"}

@app.get("/readyz")
async def readiness() -> dict[str, str]:
    """Non-secret deployment readiness signal; credentials are validated on use."""
    required = {"supabase": bool(settings.supabase_url and settings.supabase_service_role_key), "auth": bool(settings.supabase_jwt_issuer), "gemini": bool(settings.gemini_api_key), "paypal_sandbox": bool(settings.paypal_client_id and settings.paypal_client_secret and settings.paypal_webhook_id)}
    if not all(required.values()):
        raise HTTPException(503, {"status":"not_ready", "missing":[name for name, configured in required.items() if not configured]})
    try:
        settings.validate_sandbox()
    except RuntimeError as exc:
        raise HTTPException(503, {"status":"not_ready", "missing":[str(exc)]}) from exc
    return {"status":"ready"}

@app.get("/api/v1/catalog/products")
async def products() -> list: return CATALOG

@app.post("/api/v1/purchase-requests", response_model=WorkflowResponse)
async def create_purchase_request(payload: CreatePurchaseRequest, user: CurrentUser = Depends(current_user), _: None = Depends(rate_limit)) -> WorkflowResponse:
    request = PurchaseRequest(user_id=user.id, **payload.model_dump())
    return await orchestrator.process(request)

@app.post("/api/v1/purchase-requests/{request_id}/select")
async def select_recommendation(request_id: UUID, selection: RecommendationSelection, user: CurrentUser = Depends(current_user)):
    try: return await orchestrator.select_recommendation(str(request_id), selection, user.id)
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc: raise HTTPException(409, str(exc)) from exc

@app.post("/api/v1/approvals/{approval_id}")
async def decide_approval(approval_id: UUID, decision: ApprovalDecision, user: CurrentUser = Depends(current_user)) -> dict[str, str]:
    approval = await repo.get_approval(str(approval_id))
    if not approval: raise HTTPException(404, "Approval not found")
    if approval.user_id != user.id: raise HTTPException(403, "Approval does not belong to current user")
    approval.status = ApprovalStatus.approved if decision.approved else ApprovalStatus.rejected
    await repo.save_approval(approval)
    await repo.audit(approval.user_id, "payment_approval", str(approval.id), f"approval_{approval.status.value}", after_state={"status":approval.status.value})
    return {"status": approval.status.value}

@app.post("/api/payments/create-order", response_model=PayPalOrderView)
async def create_paypal_order(payload: CreateOrderRequest, user: CurrentUser = Depends(current_user)) -> PayPalOrderView:
    approval = await repo.get_approval(str(payload.approval_id))
    if not approval: raise HTTPException(404, "Approval not found")
    if approval.user_id != user.id: raise HTTPException(403, "Approval does not belong to current user")
    product = next((p for p in CATALOG if p.id == approval.product_id), None)
    if not product: raise HTTPException(409, "Server catalog product no longer exists")
    try: return await payment_agent.create_order(approval, product)
    except PermissionError as exc: raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc

@app.get("/api/payments/{order_id}", response_model=PayPalOrderView)
async def get_paypal_order(order_id: str, user: CurrentUser = Depends(current_user)) -> PayPalOrderView:
    payment = await repo.payment_for_order(order_id)
    if not payment: raise HTTPException(404, "Unknown AgentPay PayPal order")
    if payment.user_id != user.id: raise HTTPException(403, "Payment does not belong to current user")
    try: return await payment_agent.get_order(order_id)
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc: raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc

@app.post("/api/payments/{order_id}/capture", response_model=PayPalOrderView)
async def capture_paypal_order(order_id: str, user: CurrentUser = Depends(current_user)) -> PayPalOrderView:
    payment = await repo.payment_for_order(order_id)
    if not payment: raise HTTPException(404, "Unknown AgentPay PayPal order")
    if payment.user_id != user.id: raise HTTPException(403, "Payment does not belong to current user")
    approval = await repo.get_approval(str(payment.approval_id))
    if not approval: raise HTTPException(409, "Approval record not found")
    try: return await payment_agent.capture(order_id, approval)
    except PermissionError as exc: raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc

@app.post("/api/payments/webhook")
async def paypal_webhook(request: Request) -> dict[str, str]:
    event = await request.json()
    try:
        verified = await payment_agent.verify_webhook(dict(request.headers), event)
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
    if not verified: raise HTTPException(400, "Invalid PayPal webhook signature")
    event_id = event.get("id")
    if not event_id: raise HTTPException(400, "Webhook event has no id")
    if await repo.claim_webhook(event_id, event.get("event_type", "unknown"), event): await payment_agent.reconcile_webhook(event)
    return {"status":"accepted"}
