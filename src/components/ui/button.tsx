import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "secondary" | "ghost" | "outline" | "danger"; size?: "default" | "sm" | "icon" };
export const Button = forwardRef<HTMLButtonElement, Props>(({ className, variant = "default", size = "default", ...props }, ref) => (
  <button ref={ref} className={cn("inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 disabled:pointer-events-none disabled:opacity-50", { "bg-violet-500 text-white shadow-lg shadow-violet-950/30 hover:bg-violet-400 active:scale-[.98]": variant === "default", "bg-slate-800 text-slate-100 hover:bg-slate-700": variant === "secondary", "text-slate-300 hover:bg-white/5 hover:text-white": variant === "ghost", "border border-white/10 bg-white/[.02] text-slate-200 hover:bg-white/[.06]": variant === "outline", "bg-rose-500/15 text-rose-300 hover:bg-rose-500/25": variant === "danger", "h-10 px-4 text-sm": size === "default", "h-8 px-3 text-xs": size === "sm", "h-10 w-10": size === "icon" }, className)} {...props} />
));
Button.displayName = "Button";
