"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

type Rule = {
  id: number;
  name: string;
  rule_type: string;
  threshold: number;
  action_value: number;
  status: string;
};

export default function SubRulesPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);

  const [items, setItems] = useState<Rule[]>([]);
  const [name, setName] = useState("Stop Loss");
  const [ruleType, setRuleType] = useState("stop_loss");
  const [threshold, setThreshold] = useState("100");
  const [actionValue, setActionValue] = useState("0");
  const [error, setError] = useState("");

  async function loadRules() {
    setError("");
    try {
      const result = await apiRequest<{ items: Rule[] }>(`/rules/${clientId}`);
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot încărca regulile");
    }
  }

  useEffect(() => {
    if (Number.isFinite(clientId)) void loadRules();
  }, [clientId]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await apiRequest(`/rules/${clientId}`, {
        method: "POST",
        body: JSON.stringify({
          name,
          rule_type: ruleType,
          threshold: Number(threshold),
          action_value: Number(actionValue),
          status: "active",
        }),
      });
      await loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot crea regula");
    }
  }

  async function evaluateRules() {
    setError("");
    try {
      await apiRequest(`/rules/${clientId}/evaluate`, { method: "POST" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot evalua regulile");
    }
  }

  return (
    <ProtectedPage>
      <AppShell title="Reguli">
        {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}

        <form onSubmit={onCreate} className="wm-card mb-5 grid gap-3 p-4 md:grid-cols-5">
          <input className="wm-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" required />
          <select className="wm-input" value={ruleType} onChange={(e) => setRuleType(e.target.value)}>
            <option value="stop_loss">stop_loss</option>
            <option value="auto_scale">auto_scale</option>
          </select>
          <input className="wm-input" type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
          <input className="wm-input" type="number" value={actionValue} onChange={(e) => setActionValue(e.target.value)} />
          <button className="wm-btn-primary disabled:opacity-50" disabled={readOnly} title={readOnly ? "Read-only" : undefined}>Create rule</button>
        </form>

        <button
          className="wm-btn-primary mb-4 disabled:opacity-50"
          onClick={evaluateRules}
          disabled={readOnly}
          title={readOnly ? "Read-only" : undefined}
        >
          Evaluate rules
        </button>

        <section className="wm-card overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Threshold</th>
                <th className="px-4 py-3">Action Value</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((rule) => (
                <tr key={rule.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">{rule.name}</td>
                  <td className="px-4 py-3">{rule.rule_type}</td>
                  <td className="px-4 py-3">{rule.threshold}</td>
                  <td className="px-4 py-3">{rule.action_value}</td>
                  <td className="px-4 py-3">{rule.status}</td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-3 text-slate-500">Nu există reguli.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>
      </AppShell>
    </ProtectedPage>
  );
}
