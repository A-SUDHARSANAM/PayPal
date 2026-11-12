import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={cn("rounded-2xl border border-white/[.08] bg-[#10182c]/80 shadow-2xl shadow-slate-950/20", className)} {...props} />; }
