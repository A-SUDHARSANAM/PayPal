"""PayPal Orders v2 client. No LLM participates in this module."""
import asyncio
import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import httpx
from ..config import Settings
from ..models import ApprovalStatus, PayPalOrderView, PaymentRecord, PaymentStatus, PendingApproval, Product
from ..repository import MemoryRepository


def minor_to_value(amount_minor: int) -> str:
    return f"{amount_minor // 100}.{amount_minor % 100:02d}"


def provider_status(value: str) -> PaymentStatus:
    return {"CREATED": PaymentStatus.created, "SAVED": PaymentStatus.pending, "APPROVED": PaymentStatus.approved, "COMPLETED": PaymentStatus.captured, "VOIDED": PaymentStatus.cancelled, "PAYER_ACTION_REQUIRED": PaymentStatus.pending, "PENDING": PaymentStatus.pending, "DECLINED": PaymentStatus.declined}.get(value, PaymentStatus.failed)


class PaymentAgent:
    """Server-only Orders v2 integration, locked to PayPal Sandbox."""
    def __init__(self, settings: Settings, repo: MemoryRepository) -> None:
        self.settings, self.repo = settings, repo
        self._token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)
        self._token_lock = asyncio.Lock()
        self._capture_locks: dict[str, asyncio.Lock] = {}

    def _validate_config(self) -> None:
        self.settings.validate_sandbox()
        if not self.settings.paypal_client_id or not self.settings.paypal_client_secret:
            raise RuntimeError("PayPal Sandbox credentials are not configured")

    async def _access_token(self) -> str:
        self._validate_config()
        async with self._token_lock:
            if self._token and datetime.now(UTC) < self._token_expires_at:
                return self._token
            raw = f"{self.settings.paypal_client_id}:{self.settings.paypal_client_secret}".encode()
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.post(f"{self.settings.paypal_base_url}/v1/oauth2/token", headers={"Authorization": f"Basic {base64.b64encode(raw).decode()}", "Accept":"application/json", "Accept-Language":"en_US"}, data={"grant_type":"client_credentials"})
                response.raise_for_status(); data = response.json()
            self._token = data["access_token"]
            self._token_expires_at = datetime.now(UTC) + timedelta(seconds=max(0, int(data.get("expires_in", 300)) - 60))
            return self._token

    async def _request(self, method: str, path: str, *, body: dict | None = None, request_id: str | None = None) -> dict:
        token = await self._access_token()
        headers = {"Authorization":f"Bearer {token}", "Content-Type":"application/json", "Prefer":"return=representation"}
        if request_id: headers["PayPal-Request-Id"] = request_id
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.request(method, f"{self.settings.paypal_base_url}{path}", headers=headers, json=body)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _approval_url(payload: dict) -> str | None:
        return next((link.get("href") for link in payload.get("links", []) if link.get("rel") in {"payer-action", "approve"}), None)

    async def create_order(self, approval: PendingApproval, product: Product) -> PayPalOrderView:
        if approval.status != ApprovalStatus.approved:
            raise PermissionError("A verified human approval is required before creating a PayPal order")
        if approval.product_id != product.id or approval.amount_minor != product.price_minor or approval.currency != product.currency:
            raise PermissionError("Approval does not match the server-owned catalog product and price")
        existing = await self.repo.payment_for_approval(str(approval.id))
        if existing and existing.paypal_order_id:
            return PayPalOrderView(order_id=existing.paypal_order_id, status=existing.status, paypal_status=existing.status.value)
        payment = existing or PaymentRecord(approval_id=approval.id, user_id=approval.user_id, product_id=product.id, amount_minor=product.price_minor, currency=product.currency, idempotency_key=str(uuid4()))
        payload = {"intent":"CAPTURE", "purchase_units":[{"reference_id":str(approval.id), "custom_id":str(payment.id), "description":f"AgentPay demo catalog: {product.name}", "amount":{"currency_code":product.currency, "value":minor_to_value(product.price_minor)}}]}
        if self.settings.paypal_return_url and self.settings.paypal_cancel_url:
            payload["payment_source"] = {"paypal":{"experience_context":{"return_url":self.settings.paypal_return_url, "cancel_url":self.settings.paypal_cancel_url, "user_action":"PAY_NOW"}}}
        result = await self._request("POST", "/v2/checkout/orders", body=payload, request_id=payment.idempotency_key)
        payment.paypal_order_id = result["id"]
        payment.status = provider_status(result.get("status", "CREATED"))
        await self.repo.save_payment(payment)
        await self.repo.audit(approval.user_id, "transaction", str(payment.id), "paypal_order_created", after_state={"paypal_order_id":payment.paypal_order_id, "status":payment.status.value})
        return PayPalOrderView(order_id=result["id"], status=payment.status, paypal_status=result.get("status", "CREATED"), approval_url=self._approval_url(result))

    async def get_order(self, order_id: str) -> PayPalOrderView:
        payment = await self.repo.payment_for_order(order_id)
        if not payment: raise LookupError("Unknown AgentPay PayPal order")
        result = await self._request("GET", f"/v2/checkout/orders/{order_id}")
        self._assert_provider_order(result, payment)
        payment.status = provider_status(result.get("status", ""))
        capture = self._capture_id(result)
        if capture: payment.paypal_capture_id = capture
        await self.repo.save_payment(payment)
        return PayPalOrderView(order_id=order_id, status=payment.status, paypal_status=result.get("status", ""), approval_url=self._approval_url(result), capture_id=capture)

    async def capture(self, order_id: str, approval: PendingApproval) -> PayPalOrderView:
        lock = self._capture_locks.setdefault(order_id, asyncio.Lock())
        async with lock:
            return await self._capture_locked(order_id, approval)

    async def _capture_locked(self, order_id: str, approval: PendingApproval) -> PayPalOrderView:
        payment = await self.repo.payment_for_order(order_id)
        if not payment: raise LookupError("Unknown AgentPay PayPal order")
        if payment.approval_id != approval.id or approval.status != ApprovalStatus.approved:
            raise PermissionError("Capture requires the matching verified approval")
        if payment.status == PaymentStatus.captured:
            return PayPalOrderView(order_id=order_id, status=payment.status, paypal_status="COMPLETED", capture_id=payment.paypal_capture_id)
        current = await self._request("GET", f"/v2/checkout/orders/{order_id}")
        self._assert_provider_order(current, payment)
        if current.get("status") != "APPROVED":
            payment.status = provider_status(current.get("status", "")); await self.repo.save_payment(payment)
            raise PermissionError(f"PayPal order is not buyer-approved (status: {current.get('status')})")
        payment.status = PaymentStatus.capture_pending; await self.repo.save_payment(payment)
        result = await self._request("POST", f"/v2/checkout/orders/{order_id}/capture", body={}, request_id=payment.idempotency_key)
        self._assert_provider_order(result, payment)
        payment.status = provider_status(result.get("status", "")); payment.paypal_capture_id = self._capture_id(result)
        await self.repo.save_payment(payment)
        await self.repo.audit(approval.user_id, "transaction", str(payment.id), "paypal_capture_result", after_state={"paypal_order_id":order_id, "paypal_capture_id":payment.paypal_capture_id, "status":payment.status.value})
        return PayPalOrderView(order_id=order_id, status=payment.status, paypal_status=result.get("status", ""), capture_id=payment.paypal_capture_id)

    async def verify_webhook(self, headers: dict[str, str], event: dict) -> bool:
        if not self.settings.paypal_webhook_id: raise RuntimeError("PAYPAL_WEBHOOK_ID is required for webhook verification")
        names = {key.lower(): value for key, value in headers.items()}
        required = ["paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id", "paypal-transmission-sig", "paypal-transmission-time"]
        if any(not names.get(key) for key in required): return False
        result = await self._request("POST", "/v1/notifications/verify-webhook-signature", body={"auth_algo":names["paypal-auth-algo"], "cert_url":names["paypal-cert-url"], "transmission_id":names["paypal-transmission-id"], "transmission_sig":names["paypal-transmission-sig"], "transmission_time":names["paypal-transmission-time"], "webhook_id":self.settings.paypal_webhook_id, "webhook_event":event})
        return result.get("verification_status") == "SUCCESS"

    async def reconcile_webhook(self, event: dict) -> None:
        resource = event.get("resource", {}); order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id") or resource.get("id")
        payment = await self.repo.payment_for_order(order_id) if order_id else None
        if not payment: return
        event_type = event.get("event_type", "")
        status_map = {"CHECKOUT.ORDER.APPROVED":PaymentStatus.approved, "PAYMENT.CAPTURE.COMPLETED":PaymentStatus.captured, "PAYMENT.CAPTURE.DENIED":PaymentStatus.declined, "PAYMENT.CAPTURE.DECLINED":PaymentStatus.declined, "PAYMENT.CAPTURE.PENDING":PaymentStatus.pending, "PAYMENT.CAPTURE.REFUNDED":PaymentStatus.failed}
        if event_type in status_map: payment.status = status_map[event_type]
        if event_type.startswith("PAYMENT.CAPTURE."): payment.paypal_capture_id = resource.get("id") or payment.paypal_capture_id
        await self.repo.save_payment(payment)
        await self.repo.audit(None, "transaction", str(payment.id), "paypal_webhook_reconciled", after_state={"event_type":event_type, "status":payment.status.value, "paypal_capture_id":payment.paypal_capture_id})

    @staticmethod
    def _capture_id(payload: dict) -> str | None:
        captures = payload.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [])
        return captures[0].get("id") if captures else None

    @staticmethod
    def _assert_provider_order(payload: dict, payment: PaymentRecord) -> None:
        unit = (payload.get("purchase_units") or [{}])[0]; amount = unit.get("amount", {})
        if payload.get("id") != payment.paypal_order_id or unit.get("reference_id") != str(payment.approval_id) or amount.get("currency_code") != payment.currency or amount.get("value") != minor_to_value(payment.amount_minor):
            raise PermissionError("PayPal order does not match the canonical AgentPay payment record")
