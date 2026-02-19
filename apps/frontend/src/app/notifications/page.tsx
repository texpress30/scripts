"use client";

import { useState } from "react";
import {
  Bell,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  Info,
  Trash2,
  CheckCheck,
  Filter,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { cn } from "@/lib/utils";

type NotificationType = "alert" | "success" | "warning" | "info";

type Notification = {
  id: number;
  title: string;
  message: string;
  type: NotificationType;
  read: boolean;
  timestamp: string;
  client?: string;
};

const typeConfig: Record<
  NotificationType,
  { icon: typeof Bell; bgClass: string; iconClass: string; dotClass: string }
> = {
  alert: {
    icon: TrendingDown,
    bgClass: "bg-rose-50 dark:bg-rose-950/30",
    iconClass: "text-rose-600 dark:text-rose-400",
    dotClass: "bg-rose-500",
  },
  success: {
    icon: TrendingUp,
    bgClass: "bg-emerald-50 dark:bg-emerald-950/30",
    iconClass: "text-emerald-600 dark:text-emerald-400",
    dotClass: "bg-emerald-500",
  },
  warning: {
    icon: AlertTriangle,
    bgClass: "bg-amber-50 dark:bg-amber-950/30",
    iconClass: "text-amber-600 dark:text-amber-400",
    dotClass: "bg-amber-500",
  },
  info: {
    icon: Info,
    bgClass: "bg-indigo-50 dark:bg-indigo-950/30",
    iconClass: "text-indigo-600 dark:text-indigo-400",
    dotClass: "bg-indigo-500",
  },
};

// Placeholder data — replace with apiRequest calls to your FastAPI backend
const placeholderNotifications: Notification[] = [
  {
    id: 1,
    title: "Buget epuizat 85%",
    message:
      "Bugetul campaniei Google Ads pentru Acme Corp a atins 85%. Verifica si ajusteaza limita.",
    type: "warning",
    read: false,
    timestamp: "Acum 5 min",
    client: "Acme Corp",
  },
  {
    id: 2,
    title: "ROAS crescut cu 23%",
    message:
      "Campania Meta Ads pentru TechStart SRL a inregistrat o crestere semnificativa a ROAS-ului in ultimele 7 zile.",
    type: "success",
    read: false,
    timestamp: "Acum 1 ora",
    client: "TechStart SRL",
  },
  {
    id: 3,
    title: "Conversii scazute",
    message:
      "Numarul de conversii pentru FreshBite a scazut cu 18% fata de saptamana trecuta pe Google Ads.",
    type: "alert",
    read: false,
    timestamp: "Acum 2 ore",
    client: "FreshBite",
  },
  {
    id: 4,
    title: "Creative aprobat",
    message:
      'Asset-ul "Banner campanie vara 2025" a fost aprobat si este activ in campania Google Ads.',
    type: "success",
    read: true,
    timestamp: "Acum 4 ore",
    client: "Acme Corp",
  },
  {
    id: 5,
    title: "Raport saptamanal disponibil",
    message:
      "Raportul de performanta saptamanal pentru toti clientii este gata de descarcat.",
    type: "info",
    read: true,
    timestamp: "Ieri",
  },
  {
    id: 6,
    title: "Cost per click crescut",
    message:
      "CPC-ul mediu pe Meta Ads pentru TechStart SRL a crescut cu 15% fata de luna anterioara.",
    type: "warning",
    read: true,
    timestamp: "Ieri",
    client: "TechStart SRL",
  },
  {
    id: 7,
    title: "Campanie noua lansata",
    message:
      'Campania "Promo Vara 2025" pentru FreshBite a fost lansata cu succes pe ambele platforme.',
    type: "info",
    read: true,
    timestamp: "Acum 2 zile",
    client: "FreshBite",
  },
];

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>(
    placeholderNotifications
  );
  const [filterType, setFilterType] = useState<string>("all");

  const unreadCount = notifications.filter((n) => !n.read).length;

  const filtered = notifications.filter((n) => {
    if (filterType === "all") return true;
    if (filterType === "unread") return !n.read;
    return n.type === filterType;
  });

  const markAsRead = (id: number) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const markAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const deleteNotification = (id: number) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  return (
    <ProtectedPage>
      <AppShell title="Notificari">
        <div className="mb-6">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Alerte si notificari despre performanta campaniilor, buget si
            asset-uri creative.
          </p>
        </div>

        {/* Stats row */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            {
              label: "Total",
              value: notifications.length,
              color: "text-slate-900 dark:text-slate-100",
            },
            {
              label: "Necitite",
              value: unreadCount,
              color: "text-indigo-600 dark:text-indigo-400",
            },
            {
              label: "Alerte",
              value: notifications.filter((n) => n.type === "alert").length,
              color: "text-rose-600 dark:text-rose-400",
            },
            {
              label: "Atentionari",
              value: notifications.filter((n) => n.type === "warning").length,
              color: "text-amber-600 dark:text-amber-400",
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className="mcc-card flex flex-col gap-1 p-4"
            >
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {stat.label}
              </span>
              <span className={cn("text-2xl font-semibold", stat.color)}>
                {stat.value}
              </span>
            </div>
          ))}
        </div>

        {/* Toolbar */}
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-slate-400" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="mcc-input h-9 w-auto text-sm"
            >
              <option value="all">Toate</option>
              <option value="unread">Necitite</option>
              <option value="alert">Alerte</option>
              <option value="warning">Atentionari</option>
              <option value="success">Succes</option>
              <option value="info">Informative</option>
            </select>
          </div>
          {unreadCount > 0 && (
            <button
              onClick={markAllAsRead}
              className="mcc-btn-secondary gap-2 text-sm"
            >
              <CheckCheck className="h-4 w-4" />
              Marcheaza toate ca citite
            </button>
          )}
        </div>

        {/* Notifications list */}
        <div className="space-y-2">
          {filtered.map((notification) => {
            const config = typeConfig[notification.type];
            const Icon = config.icon;

            return (
              <div
                key={notification.id}
                onClick={() => markAsRead(notification.id)}
                className={cn(
                  "mcc-card group flex cursor-pointer gap-4 p-4 transition-colors hover:border-slate-300 dark:hover:border-slate-600",
                  !notification.read &&
                    "border-l-2 border-l-indigo-500 dark:border-l-indigo-400"
                )}
              >
                {/* Icon */}
                <div
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                    config.bgClass
                  )}
                >
                  <Icon className={cn("h-5 w-5", config.iconClass)} />
                </div>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <h3
                        className={cn(
                          "text-sm",
                          !notification.read
                            ? "font-semibold text-slate-900 dark:text-slate-100"
                            : "font-medium text-slate-700 dark:text-slate-300"
                        )}
                      >
                        {notification.title}
                      </h3>
                      {!notification.read && (
                        <span
                          className={cn(
                            "h-2 w-2 shrink-0 rounded-full",
                            config.dotClass
                          )}
                        />
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="text-xs text-slate-400 dark:text-slate-500">
                        {notification.timestamp}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteNotification(notification.id);
                        }}
                        className="rounded-md p-1 text-slate-400 opacity-0 transition-all hover:bg-rose-50 hover:text-rose-500 group-hover:opacity-100 dark:hover:bg-rose-950/30 dark:hover:text-rose-400"
                        title="Sterge notificarea"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    {notification.message}
                  </p>
                  {notification.client && (
                    <span className="mt-2 inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                      {notification.client}
                    </span>
                  )}
                </div>
              </div>
            );
          })}

          {filtered.length === 0 && (
            <div className="mcc-card flex flex-col items-center justify-center py-12 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800">
                <CheckCircle2 className="h-6 w-6 text-emerald-500" />
              </div>
              <p className="mt-3 text-sm font-medium text-slate-700 dark:text-slate-300">
                Nicio notificare
              </p>
              <p className="mt-1 text-xs text-slate-400">
                {filterType !== "all"
                  ? "Nu exista notificari pentru filtrul selectat."
                  : "Esti la zi cu toate alertele."}
              </p>
            </div>
          )}
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
