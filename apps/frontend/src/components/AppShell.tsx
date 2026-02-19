"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
<<<<<<< v0/texpress30-960bc9d4
import { useTheme } from "next-themes";
import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Users,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Moon,
  Sun,
  Activity,
  BarChart3,
  Settings,
  Bell,
  Search,
  Palette,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/clients", label: "Clienti", icon: Users },
  { href: "/creative", label: "Creative", icon: Palette },
=======

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/clients", label: "Clienți" },
  { href: "/login", label: "Logout" }
>>>>>>> main
];

export function AppShell({ title, children }: { title: string; children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 md:grid-cols-[240px_1fr]">
        <aside className="border-r border-slate-200 bg-white p-5">
          <h1 className="mb-6 text-lg font-bold text-purple-700">Windmill-style MCC</h1>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`block rounded-lg px-3 py-2 text-sm font-medium transition ${
                    active ? "bg-purple-100 text-purple-700" : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="p-6">
          <header className="mb-6 flex items-center justify-between">
            <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}
