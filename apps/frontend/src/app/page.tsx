import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col items-center justify-center gap-6 p-8 text-center">
      <h1 className="text-4xl font-bold text-slate-900">MCC Platform Frontend</h1>
      <p className="max-w-xl text-slate-600">
        Frontend setup pentru login, dashboard și management clienți.
      </p>
      <div className="flex gap-3">
        <Link href="/login" className="rounded bg-brand-500 px-4 py-2 font-medium text-white hover:bg-brand-600">
          Login
        </Link>
        <Link href="/dashboard" className="rounded border border-slate-300 px-4 py-2 font-medium text-slate-800">
          Dashboard
        </Link>
      </div>
    </main>
  );
}
