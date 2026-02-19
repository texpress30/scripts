import Link from "next/link";
import { Activity, ArrowRight, BarChart3, Users } from "lucide-react";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background p-8">
      <div className="flex max-w-lg flex-col items-center text-center">
        {/* Logo */}
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-primary shadow-lg shadow-primary/20">
          <Activity className="h-6 w-6 text-primary-foreground" />
        </div>

        <h1 className="text-balance text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          MCC Command Center
        </h1>
        <p className="mt-3 max-w-md text-pretty text-muted-foreground">
          Platforma enterprise de monitorizare si optimizare pentru agentii de marketing digital.
        </p>

        {/* Action buttons */}
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link href="/login" className="mcc-btn-primary gap-2 px-6 py-2.5">
            Intra in platforma
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/dashboard" className="mcc-btn-secondary gap-2 px-6 py-2.5">
            <BarChart3 className="h-4 w-4" />
            Dashboard
          </Link>
        </div>

        {/* Feature highlights */}
        <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <FeatureCard
            icon={BarChart3}
            title="Analytics"
            description="Monitorizare Google Ads si Meta Ads in timp real"
          />
          <FeatureCard
            icon={Users}
            title="Multi-Client"
            description="Gestioneaza mai multi clienti dintr-un singur loc"
          />
          <FeatureCard
            icon={Activity}
            title="Performance"
            description="Recomandari AI pentru optimizarea bugetelor"
          />
        </div>
      </div>
    </main>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof Activity;
  title: string;
  description: string;
}) {
  return (
    <div className="mcc-card p-4 text-left">
      <div className="mb-2 rounded-md bg-primary/10 p-1.5 w-fit">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{description}</p>
    </div>
  );
}
