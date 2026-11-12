"use client";
import { AppShell, type Page } from "@/components/app-shell";
import { AgentsPage, ConnectedApprovalPage, ConnectedPurchasePage, Dashboard, SettingsPage, TransactionsPage } from "@/components/dashboard-pages";
import { useState } from "react";
import type { Approval, PaymentOrder, WorkflowResponse } from "@/lib/agentpay-api";

export default function Home() {
  const [page, setPage] = useState<Page>("dashboard");
  const [flow, setFlow] = useState<WorkflowResponse>();
  const [approval, setApproval] = useState<Approval>();
  const [payment, setPayment] = useState<PaymentOrder>();
  const content = page === "dashboard" ? <Dashboard setPage={setPage}/> : page === "chat" ? <ConnectedPurchasePage onApprovalReady={(nextFlow, nextApproval) => { setFlow(nextFlow); setApproval(nextApproval); setPage("approvals"); }}/> : page === "agents" ? <AgentsPage/> : page === "approvals" ? <ConnectedApprovalPage key={approval?.id} flow={flow} approval={approval} onPaymentResult={setPayment}/> : page === "transactions" ? <TransactionsPage payment={payment}/> : <SettingsPage/>;
  return <AppShell page={page} setPage={setPage}>{content}</AppShell>;
}
