"use client";

import React, { FormEvent, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

type TeamUserForm = {
  prenume: string;
  nume: string;
  email: string;
  telefon: string;
  extensie: string;
  parola: string;
  semnatura: string;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function SubAccountTeamPage() {
  const params = useParams<{ id: string }>();

  const [form, setForm] = useState<TeamUserForm>({
    prenume: "",
    nume: "",
    email: "",
    telefon: "",
    extensie: "",
    parola: "",
    semnatura: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showAdvanced, setShowAdvanced] = useState(false);

  const tabs = useMemo(
    () => [
      { key: "informatii", label: "Informații Utilizator", active: true },
      { key: "roluri", label: "Roluri și Permisiuni", active: false },
      { key: "apeluri", label: "Setări Apeluri și Mesaje Vocale", active: false },
      { key: "disponibilitate", label: "Disponibilitate Utilizator", active: false },
    ],
    []
  );

  function validate(): Record<string, string> {
    const next: Record<string, string> = {};
    if (form.prenume.trim() === "") next.prenume = "Prenumele este obligatoriu.";
    if (form.nume.trim() === "") next.nume = "Numele este obligatoriu.";
    if (form.email.trim() === "") next.email = "Email-ul este obligatoriu.";
    else if (!EMAIL_RE.test(form.email.trim())) next.email = "Introdu o adresă de email validă.";
    if (form.extensie.trim() !== "" && !/^\d+$/.test(form.extensie.trim())) next.extensie = "Extensia trebuie să fie numerică.";
    return next;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
  }

  return (
    <ProtectedPage>
      <AppShell title={`Sub-account #${params.id} — Echipa Mea`}>
        <main className="p-6">
          <section className="wm-card rounded-lg p-5 shadow-sm">
            <button type="button" className="text-sm font-medium text-slate-700 hover:text-slate-900">← Înapoi</button>
            <p className="mt-2 text-sm text-slate-600">Editează sau gestionează echipa ta.</p>

            <div className="mt-5 grid grid-cols-1 gap-6 xl:grid-cols-[260px_1fr]">
              <aside className="space-y-2">
                {tabs.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    className={[
                      "w-full rounded-md px-3 py-2 text-left text-sm transition-colors",
                      tab.active ? "bg-indigo-50 font-semibold text-indigo-700" : "text-slate-700 hover:bg-slate-50",
                    ].join(" ")}
                  >
                    {tab.label}
                  </button>
                ))}
              </aside>

              <form noValidate onSubmit={submit} className="space-y-5">
                <div className="rounded-lg border border-slate-200 p-4">
                  <h2 className="text-base font-semibold text-slate-900">Informații Utilizator</h2>

                  <div className="mt-4 space-y-4">
                    <div>
                      <p className="text-sm font-medium text-slate-700">Imagine Profil</p>
                      <div className="mt-2 flex items-center gap-4">
                        <div className="h-24 w-24 rounded-full border border-slate-300 bg-slate-50" />
                        <p className="text-xs text-slate-500">Mărimea propusă este 512x512 px, nu mai mare de 2.5 MB.</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <label className="text-sm text-slate-700">
                        Prenume <span className="text-red-500">*</span>
                        <input
                          placeholder="Prenume"
                          className="wm-input mt-1"
                          value={form.prenume}
                          onChange={(e) => setForm((prev) => ({ ...prev, prenume: e.target.value }))}
                        />
                        {errors.prenume ? <p className="mt-1 text-xs text-red-600">{errors.prenume}</p> : null}
                      </label>

                      <label className="text-sm text-slate-700">
                        Nume <span className="text-red-500">*</span>
                        <input
                          placeholder="Nume"
                          className="wm-input mt-1"
                          value={form.nume}
                          onChange={(e) => setForm((prev) => ({ ...prev, nume: e.target.value }))}
                        />
                        {errors.nume ? <p className="mt-1 text-xs text-red-600">{errors.nume}</p> : null}
                      </label>

                      <label className="text-sm text-slate-700 md:col-span-2">
                        Email <span className="text-red-500">*</span>
                        <input
                          type="email"
                          placeholder="Email"
                          className="wm-input mt-1"
                          value={form.email}
                          onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                        />
                        {errors.email ? <p className="mt-1 text-xs text-red-600">{errors.email}</p> : null}
                      </label>

                      <label className="text-sm text-slate-700">
                        Telefon
                        <input
                          type="tel"
                          placeholder="Telefon"
                          className="wm-input mt-1"
                          value={form.telefon}
                          onChange={(e) => setForm((prev) => ({ ...prev, telefon: e.target.value }))}
                        />
                      </label>

                      <label className="text-sm text-slate-700">
                        Extensie
                        <input
                          inputMode="numeric"
                          placeholder="Extensie"
                          className="wm-input mt-1"
                          value={form.extensie}
                          onChange={(e) => setForm((prev) => ({ ...prev, extensie: e.target.value }))}
                        />
                        {errors.extensie ? <p className="mt-1 text-xs text-red-600">{errors.extensie}</p> : null}
                      </label>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 p-4">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between text-left text-sm font-semibold text-slate-800"
                    onClick={() => setShowAdvanced((prev) => !prev)}
                  >
                    Setări Avansate
                    <ChevronDown className={`h-4 w-4 transition-transform ${showAdvanced ? "rotate-180" : "rotate-0"}`} />
                  </button>

                  <div className={`overflow-hidden transition-all duration-300 ${showAdvanced ? "mt-3 max-h-40 opacity-100" : "max-h-0 opacity-0"}`}>
                    {showAdvanced ? (
                      <label className="block text-sm text-slate-700">
                        Parolă
                        <input
                          type="password"
                          placeholder="Parolă"
                          className="wm-input mt-1"
                          value={form.parola}
                          onChange={(e) => setForm((prev) => ({ ...prev, parola: e.target.value }))}
                        />
                      </label>
                    ) : null}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 p-4">
                  <h3 className="text-base font-semibold text-slate-900">Semnătură</h3>
                  <label className="mt-3 block text-sm text-slate-700">
                    Semnătură utilizator
                    <textarea
                      placeholder="Adaugă semnătura utilizatorului"
                      className="wm-input mt-1 min-h-24"
                      value={form.semnatura}
                      onChange={(e) => setForm((prev) => ({ ...prev, semnatura: e.target.value }))}
                    />
                  </label>
                </div>

                <div className="flex items-center justify-end gap-3">
                  <button type="button" className="wm-btn-secondary">Anulează</button>
                  <button type="submit" className="wm-btn-primary">Înainte</button>
                </div>
              </form>
            </div>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
