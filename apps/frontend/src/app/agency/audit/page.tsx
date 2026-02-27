"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type AuditEvent = {
  timestamp: string;
  actor_email: string;
  actor_role: string;
  action: string;
  resource: string;
};

type AuditResponse = { items: AuditEvent[] };

export default function AgencyAuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;

    async function loadAudit() {
      setError("");
      try {
        const result = await apiRequest<AuditResponse>("/audit");
        if (!ignore) setEvents(result.items);
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : "Nu pot încărca audit log");
      }
    }

    void loadAudit();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <ProtectedPage>
      <AppShell title="Agency Audit">
        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

        <section className="wm-card overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Resource</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={`${event.timestamp}-${event.action}-${event.resource}`} className="border-t border-slate-100">
                  <td className="px-4 py-3">{new Date(event.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3">{event.actor_email}</td>
                  <td className="px-4 py-3">{event.actor_role}</td>
                  <td className="px-4 py-3">{event.action}</td>
                  <td className="px-4 py-3">{event.resource}</td>
                </tr>
              ))}
              {events.length === 0 ? (
                <tr>
                  <td className="px-4 py-4 text-slate-500" colSpan={5}>
                    Nu există evenimente de audit.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>
      </AppShell>
    </ProtectedPage>
  );
}
