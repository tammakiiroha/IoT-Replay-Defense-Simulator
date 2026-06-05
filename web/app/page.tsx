import Link from 'next/link';
import { ArrowRight, ChartNoAxesCombined, FlaskConical, Radio, Shield } from 'lucide-react';
import { Panel, SiteShell } from '../components/site-shell';

export default function HomePage() {
  return (
    <SiteShell
      eyebrow="Replay Research Platform"
      title="One research product, two runtime modes."
      intro="The public site is a static, evidence-backed showcase with a browser-side simulator demo. The local full-stack mode runs the Python core used for Monte Carlo sweeps, physical validation, and thesis artifacts."
    >
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel
          title="North star"
          description="This repository now treats the thesis as the primary product contract: the simulator, the hardware comparison workflow, and the website all align behind one authoritative backend."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-3xl border border-stone-900/10 bg-white/70 p-5">
              <p className="eyebrow">Public deploy</p>
              <h3 className="mt-3 text-xl font-semibold">Static exhibition mode</h3>
              <p className="mt-2 text-sm leading-6 text-stone-600">
                Serves artifact-backed charts, explanations, methodology, reproducibility notes, and an
                interactive browser demo for quick scenario exploration.
              </p>
            </div>
            <div className="rounded-3xl border border-stone-900/10 bg-white/70 p-5">
              <p className="eyebrow">Local full stack</p>
              <h3 className="mt-3 text-xl font-semibold">Authoritative runtime mode</h3>
              <p className="mt-2 text-sm leading-6 text-stone-600">
                Uses FastAPI plus the Python core for live runs, sweeps, and physical experiment alignment.
              </p>
            </div>
          </div>
        </Panel>

        <Panel title="Fast navigation" description="Use the showcase as a thesis-grade story, not just a simulator form.">
          <div className="grid gap-3">
            {[
              {
                href: '/simulator',
                label: 'Authoritative Simulator',
                text: 'Run the Python-backed simulation locally and inspect the returned metrics.',
                icon: Shield,
              },
              {
                href: '/results',
                label: 'Results & Figures',
                text: 'Explore sweep datasets, generated artifacts, and published charts.',
                icon: ChartNoAxesCombined,
              },
              {
                href: '/hardware',
                label: 'Physical Validation',
                text: 'Show the bridge from simulation logic to HackRF-backed experiments.',
                icon: Radio,
              },
              {
                href: '/reproducibility',
                label: 'Reproducibility',
                text: 'Document commands, artifacts, and dataset boundaries for examiners.',
                icon: FlaskConical,
              },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="group flex items-center justify-between rounded-3xl border border-stone-900/10 bg-white/70 p-5 transition hover:-translate-y-0.5"
              >
                <div className="flex items-start gap-4">
                  <item.icon className="mt-1 h-5 w-5 text-teal-700" />
                  <div>
                    <h3 className="text-lg font-semibold text-stone-950">{item.label}</h3>
                    <p className="mt-2 max-w-md text-sm leading-6 text-stone-600">{item.text}</p>
                  </div>
                </div>
                <ArrowRight className="h-5 w-5 text-stone-400 transition group-hover:translate-x-1" />
              </Link>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Authority boundary">
          <p className="text-sm leading-7 text-stone-700">
            The browser demo is for interactive exploration. The Python runtime remains the authority for
            release artifacts, CLI/API runs, and research-grade numbers.
          </p>
        </Panel>
        <Panel title="Experiment boundary">
          <p className="text-sm leading-7 text-stone-700">
            Simulation, sweeps, and physical comparison all emit versioned artifacts with explicit metadata.
          </p>
        </Panel>
        <Panel title="Migration boundary">
          <p className="text-sm leading-7 text-stone-700">
            Legacy CLI, API, and GUI entrypoints still exist as compatibility shells while the new structure
            settles.
          </p>
        </Panel>
      </div>
    </SiteShell>
  );
}
