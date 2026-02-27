"use client";

import { FormEvent, useState } from "react";
import { Info, Pencil, Trash2, UserCircle2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function SettingsProfilePage() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("admin@example.com");
  const [phone, setPhone] = useState("");
  const [extension, setExtension] = useState("");
  const [language, setLanguage] = useState("ro");

  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  return (
    <ProtectedPage>
      <AppShell title="Settings — Personal Profile">
        <main className="p-6">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <section className="wm-card p-4 xl:col-span-2">
              <h2 className="text-lg font-semibold text-slate-900">Personal Data</h2>

              <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center">
                <div className="relative h-24 w-24 rounded-full border border-slate-200 bg-slate-50">
                  <div className="flex h-full w-full items-center justify-center text-slate-400">
                    <UserCircle2 className="h-14 w-14" />
                  </div>
                  <button className="absolute -right-1 top-1 rounded-full border border-slate-200 bg-white p-1 text-slate-500 hover:bg-slate-50" title="Editează imagine">
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button className="absolute -right-1 bottom-1 rounded-full border border-slate-200 bg-white p-1 text-slate-500 hover:bg-slate-50" title="Șterge imagine">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
                <p className="text-sm text-slate-500">The proposed size is 512*512 px no bigger than 2.5 MB</p>
              </div>

              <form className="mt-4 space-y-4" onSubmit={submitProfile}>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="text-sm text-slate-700">
                    First Name <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                    {firstName.trim() === "" ? <p className="mt-1 text-xs text-red-600">First name cannot be left blank</p> : null}
                  </label>

                  <label className="text-sm text-slate-700">
                    Last Name <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={lastName} onChange={(e) => setLastName(e.target.value)} />
                    {lastName.trim() === "" ? <p className="mt-1 text-xs text-red-600">Last name cannot be left blank</p> : null}
                  </label>

                  <label className="text-sm text-slate-700 md:col-span-2">
                    Email <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={email} onChange={(e) => setEmail(e.target.value)} />
                  </label>

                  <label className="text-sm text-slate-700">
                    Phone
                    <input className="wm-input mt-1" value={phone} onChange={(e) => setPhone(e.target.value)} />
                  </label>

                  <label className="text-sm text-slate-700">
                    Extension
                    <input className="wm-input mt-1" value={extension} onChange={(e) => setExtension(e.target.value)} />
                  </label>

                  <label className="text-sm text-slate-700 md:col-span-2">
                    Platform Language
                    <select className="wm-input mt-1" value={language} onChange={(e) => setLanguage(e.target.value)}>
                      <option value="ro">Română</option>
                      <option value="en-US">English (United States)</option>
                    </select>
                  </label>
                </div>

                <div className="flex justify-end">
                  <button className="wm-btn-primary" type="submit">Update Profile</button>
                </div>
              </form>
            </section>

            <section className="space-y-4">
              <article className="wm-card p-4">
                <h3 className="text-base font-semibold text-slate-900">Change Password</h3>
                <form className="mt-3 space-y-3" onSubmit={submitPassword}>
                  <label className="block text-sm text-slate-700">
                    Current Password <span className="text-red-500">*</span>
                    <input type="password" className="wm-input mt-1" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
                  </label>
                  <label className="block text-sm text-slate-700">
                    Password <span className="text-red-500">*</span>
                    <input type="password" className="wm-input mt-1" value={password} onChange={(e) => setPassword(e.target.value)} />
                  </label>
                  <label className="block text-sm text-slate-700">
                    Confirm Password <span className="text-red-500">*</span>
                    <input type="password" className="wm-input mt-1" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
                  </label>
                  <div className="flex justify-end">
                    <button className="wm-btn-primary" type="submit">Update Password</button>
                  </div>
                </form>
              </article>

              <article className="wm-card p-4">
                <h3 className="text-base font-semibold text-slate-900">Sign Out Everywhere</h3>
                <p className="mt-2 text-sm text-slate-600">This will sign you out of all devices and sessions, including this one.</p>
                <div className="mt-3 flex justify-end">
                  <button className="wm-btn-primary" type="button">Sign Out Everywhere</button>
                </div>
              </article>

              <article className="wm-card p-4">
                <h3 className="flex items-center gap-2 text-base font-semibold text-slate-900">
                  Two-factor Authentication (2FA) App
                  <span title="Use a 2FA authenticator app for additional account protection." className="text-slate-400">
                    <Info className="h-4 w-4" />
                  </span>
                </h3>
                <p className="mt-2 text-sm text-slate-600">Strengthen account security by requiring a one-time code from an authenticator app at sign-in.</p>
                <div className="mt-3">
                  <button className="wm-btn-secondary" type="button">Setup Two-factor Authentication (2FA) App</button>
                </div>
              </article>
            </section>
          </div>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
