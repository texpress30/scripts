import Link from "next/link";
import { Activity, ArrowRight, BarChart3, Users } from "lucide-react";

const highlights = [
  {
    icon: BarChart3,
    title: "Analytics",
    description: "Monitorizare Google Ads si Meta Ads in timp real"
  },
  {
    icon: Users,
    title: "Multi-Client",
    description: "Gestioneaza mai multi clienti dintr-un singur loc"
  },
  {
    icon: Activity,
    title: "Performance",
    description: "Recomandari AI pentru optimizarea bugetelor"
  }
];

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-16">
      <div className="mx-auto w-full max-w-2xl text-center">
        <div className="mx-auto mb-8 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-600 shadow-lg shadow-indigo-600/25">
          <Activity className="h-8 w-8 text-white" />
        </div>

        <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">OMAROSA MCC</h1>
        <p className="mx-auto mt-4 max-w-xl text-xl text-slate-600">
          Platforma enterprise de monitorizare si optimizare pentru agentii de marketing digital.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/login" className="premium-btn-primary inline-flex items-center gap-2">
            Intra in platforma
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/agency/dashboard" className="premium-btn-secondary inline-flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Dashboard
          </Link>
        </div>

        <section className="mt-14 grid grid-cols-1 gap-5 text-left md:grid-cols-3">
          {highlights.map(({ icon: Icon, title, description }) => (
            <article key={title} className="premium-card p-6">
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-100 text-indigo-600">
                <Icon className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
              <p className="mt-2 text-lg text-slate-600">{description}</p>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
