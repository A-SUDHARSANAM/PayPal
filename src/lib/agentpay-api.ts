export type FindingSeverity = "pass" | "warning" | "fail";
export type PaymentStatus = "created" | "approved" | "capture_pending" | "captured" | "cancelled" | "declined" | "failed" | "pending";
export interface Product { id: string; name: string; category: string; merchant: string; price_minor: number; currency: string; features: string[]; recurring_cost_minor: number; eligible: boolean; is_demo: true; }
export interface FinanceResult { status: FindingSeverity; total_minor: number; budget_remaining_minor: number; recurring_cost_minor: number; violations: string[]; }
export interface RiskResult { score: number; status: FindingSeverity; duplicate_detected: boolean; unusual_amount: boolean; policy_violations: string[]; explanation: string; }
export interface RankedProduct { product_id: string; score: number; reason: string; }
export interface RecommendationResult { status: FindingSeverity; ranked: RankedProduct[]; selected_product_id?: string; explanation: string; }
export interface AgentExecution { id: string; request_id: string; agent: string; status: "completed" | "failed" | "blocked"; output: Record<string, unknown>; error?: string; created_at: string; completed_at?: string; duration_ms?: number; }
export interface WorkflowResponse { request_id: string; status: "recommendation_ready" | "approval_pending" | "blocked"; research: { requirements: { category: string; keywords: string[]; desired_features: string[]; max_price_minor?: number; recurring: boolean }; products: Product[]; comparisons: Record<string, string>; }; finance: FinanceResult; risk: RiskResult; recommendation?: RecommendationResult; approval?: Approval; executions: AgentExecution[]; }
export interface Approval { id: string; purchase_request_id: string; user_id: string; product_id: string; amount_minor: number; currency: string; status: "pending" | "approved" | "rejected" | "expired" | "cancelled"; created_at: string; }
export interface PaymentOrder { order_id: string; status: PaymentStatus; paypal_status: string; approval_url?: string; capture_id?: string; }

const baseUrl = process.env.NEXT_PUBLIC_AGENTPAY_API_URL ?? "http://localhost:8000";
async function call<T>(path: string, init?: RequestInit, authenticated = true): Promise<T> {
  const token = authenticated ? await getAccessToken() : undefined;
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers }, cache: "no-store" });
  if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(body?.detail ?? `Request failed (${response.status})`); }
  return response.json() as Promise<T>;
}
export const agentPayApi = {
  createRequest: (payload: { text: string; budget_minor: number; currency: string; max_transaction_minor: number }) => call<WorkflowResponse>("/api/v1/purchase-requests", { method: "POST", body: JSON.stringify(payload) }),
  selectRecommendation: (requestId: string, productId: string) => call<Approval>(`/api/v1/purchase-requests/${requestId}/select`, { method: "POST", body: JSON.stringify({ product_id: productId }) }),
  decideApproval: (approvalId: string, approved: boolean) => call<{ status: Approval["status"] }>(`/api/v1/approvals/${approvalId}`, { method: "POST", body: JSON.stringify({ approved }) }),
  createOrder: (approvalId: string) => call<PaymentOrder>("/api/payments/create-order", { method: "POST", body: JSON.stringify({ approval_id: approvalId }) }),
  getOrder: (orderId: string) => call<PaymentOrder>(`/api/payments/${orderId}`),
  captureOrder: (orderId: string) => call<PaymentOrder>(`/api/payments/${orderId}/capture`, { method: "POST", body: "{}" }),
};
import { getAccessToken } from "@/lib/supabase-browser";
