import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col items-center justify-center gap-6 p-8 text-center">
      <h1 className="text-4xl font-bold text-slate-900">MCC Platform Frontend</h1>
      <p className="max-w-xl text-slate-600">Frontend setup pentru login, dashboard și management clienți.</p>
      <div className="flex gap-3">
        <Link href="/login" className="wm-btn-primary">
          Login
        </Link>
        <Link href="/dashboard" className="wm-btn-secondary">
          Dashboard
        </Link>
      </div>
    </main>
  );
}
