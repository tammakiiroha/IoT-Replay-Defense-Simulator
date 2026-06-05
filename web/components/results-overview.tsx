'use client';

import { startTransition, useEffect, useState } from 'react';
import Image from 'next/image';
import { ArrowRight, FileSpreadsheet, RadioTower } from 'lucide-react';
import type { ArtifactManifest, ExperimentArtifact } from '../lib/contracts';
import { loadArtifact, loadManifest } from '../lib/data';
import { withBasePath } from '../lib/site';

export function ResultsOverview() {
  const [manifest, setManifest] = useState<ArtifactManifest | null>(null);
  const [artifacts, setArtifacts] = useState<ExperimentArtifact[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const nextManifest = await loadManifest();
        const nextArtifacts = await Promise.all(
          nextManifest.artifacts.map((artifact) => loadArtifact(artifact.path))
        );
        if (!active) {
          return;
        }
        startTransition(() => {
          setManifest(nextManifest);
          setArtifacts(nextArtifacts);
        });
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load manifest');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <div className="panel">
        <p className="text-sm text-rose-700">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-3">
        {manifest?.highlights.map((highlight) => (
          <div key={String(highlight.label)} className="panel">
            <p className="eyebrow">{String(highlight.label)}</p>
            <p className="mt-3 text-lg font-semibold text-stone-950">{String(highlight.value)}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="panel">
          <div className="mb-6 flex items-center gap-3">
            <FileSpreadsheet className="h-5 w-5 text-teal-700" />
            <h3 className="text-xl font-semibold">Versioned datasets</h3>
          </div>
          <div className="space-y-4">
            {artifacts.map((artifact) => (
              <article key={artifact.artifact_id} className="rounded-3xl border border-stone-900/10 bg-white/70 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="eyebrow">{artifact.kind}</p>
                    <h4 className="mt-2 text-lg font-semibold">{artifact.title}</h4>
                    <p className="mt-2 text-sm leading-6 text-stone-600">{artifact.description}</p>
                  </div>
                  <ArrowRight className="mt-1 h-5 w-5 text-stone-400" />
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {Object.entries(artifact.summary).slice(0, 4).map(([key, value]) => (
                    <div key={key} className="rounded-2xl border border-stone-900/10 bg-stone-50/80 p-3">
                      <p className="text-[11px] uppercase tracking-[0.2em] text-stone-500">{key}</p>
                      <p className="mt-2 text-sm font-medium text-stone-950">{String(value)}</p>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="panel">
            <div className="mb-4 flex items-center gap-3">
              <RadioTower className="h-5 w-5 text-amber-700" />
              <h3 className="text-xl font-semibold">Reference figures</h3>
            </div>
            <div className="space-y-4">
              {[
                { src: '/data/security_cost_frontier.png', alt: 'Security cost frontier figure' },
                { src: '/data/p_loss_dual.png', alt: 'Loss sweep figure' },
                { src: '/data/p_reorder_dual.png', alt: 'Reordering sweep figure' },
                { src: '/data/sim_vs_hw_legit.png', alt: 'Simulation vs hardware legitimate acceptance' },
              ].map((figure) => (
                <div key={figure.src} className="overflow-hidden rounded-3xl border border-stone-900/10 bg-white/70">
                  <Image
                    src={withBasePath(figure.src)}
                    alt={figure.alt}
                    width={1200}
                    height={800}
                    className="h-auto w-full"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
