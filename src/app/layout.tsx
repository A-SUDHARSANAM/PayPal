import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "AgentPay — intelligent purchasing", description: "Multi-agent payment operations" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
