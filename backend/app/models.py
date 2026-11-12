from datetime import UTC, datetime
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Product(BaseModel):
    id: str
    name: str
    category: str
    merchant: str
    price_minor: int = Field(ge=0)
    currency: str = "USD"
    features: list[str]
    recurring_cost_minor: int = Field(default=0, ge=0)
    eligible: bool = True
    is_demo: Literal[True] = True


class PurchaseRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=3, max_length=1000)
    budget_minor: int = Field(ge=0)
    currency: str = "USD"
    max_transaction_minor: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CreatePurchaseRequest(BaseModel):
    """Untrusted client request: identity comes exclusively from the validated JWT."""
    text: str = Field(min_length=3, max_length=1000)
    budget_minor: int = Field(ge=0)
    currency: str = "USD"
    max_transaction_minor: int = Field(ge=0)


class ProductRequirement(BaseModel):
    category: str
    keywords: list[str] = Field(default_factory=list)
    desired_features: list[str] = Field(default_factory=list)
    max_price_minor: int | None = Field(default=None, ge=0)
    recurring: bool = False


class ResearchResult(BaseModel):
    requirements: ProductRequirement
    products: list[Product]
    comparisons: dict[str, str] = Field(default_factory=dict)


class FindingSeverity(str, Enum):
    pass_ = "pass"
    warning = "warning"
    fail = "fail"


class FinanceResult(BaseModel):
    status: FindingSeverity
    total_minor: int = Field(ge=0)
    budget_remaining_minor: int
    recurring_cost_minor: int = Field(ge=0)
    violations: list[str] = Field(default_factory=list)


class RiskResult(BaseModel):
    score: int = Field(ge=0, le=100)
    status: FindingSeverity
    duplicate_detected: bool = False
    unusual_amount: bool = False
    policy_violations: list[str] = Field(default_factory=list)
    explanation: str


class RankedProduct(BaseModel):
    product_id: str
    score: int = Field(ge=0, le=100)
    reason: str


class RecommendationResult(BaseModel):
    status: FindingSeverity
    ranked: list[RankedProduct]
    selected_product_id: str | None = None
    explanation: str


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class PendingApproval(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    purchase_request_id: UUID
    user_id: str
    product_id: str
    amount_minor: int
    currency: str
    status: ApprovalStatus = ApprovalStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentExecution(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    agent: str
    status: Literal["completed", "failed", "blocked"]
    output: dict = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    request_id: UUID
    status: Literal["recommendation_ready", "approval_pending", "blocked"]
    research: ResearchResult
    finance: FinanceResult
    risk: RiskResult
    recommendation: RecommendationResult | None = None
    approval: PendingApproval | None = None
    executions: list[AgentExecution] = Field(default_factory=list)


class RecommendationSelection(BaseModel):
    product_id: str


class ApprovalDecision(BaseModel):
    approved: bool


class PayPalOrder(BaseModel):
    id: str
    status: str
    approval_id: UUID
    amount_minor: int
    currency: str


class PayPalCapture(BaseModel):
    id: str
    status: str
    order_id: str


class PaymentStatus(str, Enum):
    created = "created"
    approved = "approved"
    capture_pending = "capture_pending"
    captured = "captured"
    cancelled = "cancelled"
    declined = "declined"
    failed = "failed"
    pending = "pending"


class PaymentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    approval_id: UUID
    user_id: str
    product_id: str
    amount_minor: int
    currency: str
    paypal_order_id: str | None = None
    paypal_capture_id: str | None = None
    status: PaymentStatus = PaymentStatus.created
    idempotency_key: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CreateOrderRequest(BaseModel):
    approval_id: UUID


class PayPalOrderView(BaseModel):
    order_id: str
    status: PaymentStatus
    paypal_status: str
    approval_url: str | None = None
    capture_id: str | None = None
