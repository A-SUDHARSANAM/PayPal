from datetime import UTC, datetime
import httpx
from .config import Settings
from .models import AgentExecution, PaymentRecord, PendingApproval, PurchaseRequest


class MemoryRepository:
    """Development repository. Replace with Supabase/Postgres repositories in deployment."""
    def __init__(self) -> None:
        self.requests: dict[str, PurchaseRequest] = {}
        self.approvals: dict[str, PendingApproval] = {}
        self.executions: list[AgentExecution] = []
        self.payments: dict[str, PaymentRecord] = {}
        self.webhook_ids: set[str] = set()
        self.workflows: dict[str, dict] = {}

    async def save_request(self, request: PurchaseRequest) -> None: self.requests[str(request.id)] = request
    async def save_workflow(self, request_id: str, workflow: dict) -> None: self.workflows[request_id] = workflow
    async def get_workflow(self, request_id: str) -> dict | None: return self.workflows.get(request_id)
    async def save_approval(self, approval: PendingApproval) -> None: self.approvals[str(approval.id)] = approval
    async def get_approval(self, approval_id: str) -> PendingApproval | None: return self.approvals.get(approval_id)
    async def log(self, item: AgentExecution) -> None: self.executions.append(item)
    async def audit(self, actor_user_id: str | None, entity_type: str, entity_id: str, action: str, before_state: dict | None = None, after_state: dict | None = None) -> None: pass
    async def recent_for_user(self, user_id: str) -> list[PurchaseRequest]: return [x for x in self.requests.values() if x.user_id == user_id]
    async def save_payment(self, payment: PaymentRecord) -> None:
        payment.updated_at = datetime.now(UTC); self.payments[str(payment.id)] = payment
    async def payment_for_order(self, order_id: str) -> PaymentRecord | None:
        return next((p for p in self.payments.values() if p.paypal_order_id == order_id), None)
    async def payment_for_approval(self, approval_id: str) -> PaymentRecord | None:
        return next((p for p in self.payments.values() if str(p.approval_id) == approval_id), None)
    async def claim_webhook(self, event_id: str, event_type: str = "received", payload: dict | None = None) -> bool:
        if event_id in self.webhook_ids: return False
        self.webhook_ids.add(event_id); return True


class SupabaseRepository(MemoryRepository):
    """Server-only Supabase/PostgREST persistence adapter.

    The service-role key is used only by FastAPI and is never serialized to a client.
    """
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError("Supabase URL and service role key are required")
        self.url = settings.supabase_url.rstrip("/")
        self.headers = {"apikey": settings.supabase_service_role_key, "Authorization": f"Bearer {settings.supabase_service_role_key}", "Content-Type": "application/json"}

    async def save_payment(self, payment: PaymentRecord) -> None:
        payment.updated_at = datetime.now(UTC)
        body = payment.model_dump(mode="json")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.url}/rest/v1/transactions", headers={**self.headers, "Prefer":"resolution=merge-duplicates,return=minimal"}, json=body)
            response.raise_for_status()
        self.payments[str(payment.id)] = payment

    async def save_request(self, request: PurchaseRequest) -> None:
        body = {"id":str(request.id), "user_id":request.user_id, "request_text":request.text, "budget_minor":request.budget_minor, "max_transaction_minor":request.max_transaction_minor, "currency":request.currency, "status":"submitted"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.url}/rest/v1/purchase_requests", headers={**self.headers, "Prefer":"resolution=merge-duplicates,return=minimal"}, json=body)
            response.raise_for_status()
        await super().save_request(request)

    async def save_approval(self, approval: PendingApproval) -> None:
        body = {"id":str(approval.id), "purchase_request_id":str(approval.purchase_request_id), "user_id":approval.user_id, "product_id":approval.product_id, "amount_minor":approval.amount_minor, "currency":approval.currency, "status":approval.status.value, "decision_at":approval.created_at.isoformat() if approval.status in {approval.status.approved, approval.status.rejected} else None, "created_at":approval.created_at.isoformat()}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.url}/rest/v1/payment_approvals", headers={**self.headers, "Prefer":"resolution=merge-duplicates,return=minimal"}, json=body)
            response.raise_for_status()
        await super().save_approval(approval)

    async def log(self, item: AgentExecution) -> None:
        body = {"id":str(item.id), "purchase_request_id":str(item.request_id), "agent_name":item.agent, "status":item.status, "output":item.output, "error_message":item.error, "started_at":item.created_at.isoformat(), "completed_at":item.completed_at.isoformat() if item.completed_at else None, "duration_ms":item.duration_ms}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.url}/rest/v1/agent_executions", headers={**self.headers, "Prefer":"return=minimal"}, json=body)
            response.raise_for_status()
        await super().log(item)

    async def audit(self, actor_user_id: str | None, entity_type: str, entity_id: str, action: str, before_state: dict | None = None, after_state: dict | None = None) -> None:
        body = {"actor_user_id":actor_user_id, "entity_type":entity_type, "entity_id":entity_id, "action":action, "before_state":before_state, "after_state":after_state}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.url}/rest/v1/audit_logs", headers={**self.headers, "Prefer":"return=minimal"}, json=body)
            response.raise_for_status()

    async def claim_webhook(self, event_id: str, event_type: str = "received", payload: dict | None = None) -> bool:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.url}/rest/v1/paypal_webhook_events", headers={**self.headers, "Prefer":"return=minimal"}, json={"paypal_event_id": event_id, "event_type":event_type, "payload":payload or {}})
        if response.status_code in (409, 23505): return False
        response.raise_for_status(); return True


def create_repository(settings: Settings) -> MemoryRepository:
    return SupabaseRepository(settings) if settings.supabase_url and settings.supabase_service_role_key else MemoryRepository()
