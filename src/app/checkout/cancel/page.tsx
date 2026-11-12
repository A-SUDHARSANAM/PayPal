import Link from "next/link";

export default function PayPalCancelPage() {
  return <main className="grid min-h-screen place-items-center bg-[#071020] px-6 text-slate-100"><section className="max-w-md rounded-2xl border border-amber-400/20 bg-[#10182c] p-7"><p className="text-xs font-semibold uppercase tracking-[.18em] text-amber-300">PayPal Sandbox</p><h1 className="mt-3 text-2xl font-semibold">Checkout cancelled</h1><p className="mt-3 text-sm leading-relaxed text-slate-400">No payment was captured. You can return to AgentPay to review or cancel the pending request.</p><Link className="mt-6 inline-block rounded-xl bg-slate-800 px-4 py-2 text-sm font-medium text-white" href="/">Return to AgentPay</Link></section></main>;
}
