import Link from 'next/link';
import type { ReactNode } from 'react';

const NAV = [
  { href: '/', label: 'Overview' },
  { href: '/simulator', label: 'Simulator' },
  { href: '/results', label: 'Results' },
  { href: '/methodology', label: 'Methodology' },
  { href: '/hardware', label: 'Hardware' },
  { href: '/reproducibility', label: 'Reproducibility' },
];

export function SiteShell({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#f9f4e8_0%,#f5efe0_36%,#ebe3d2_100%)] text-stone-900">
      <header className="border-b border-stone-900/10 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <p className="eyebrow">{eyebrow}</p>
            <h1 className="text-4xl font-semibold tracking-[-0.04em] text-stone-950 lg:text-6xl">
              {title}
            </h1>
            <p className="max-w-2xl text-base leading-7 text-stone-700 lg:text-lg">{intro}</p>
          </div>
          <nav className="flex flex-wrap gap-2">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className="nav-pill">
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10">{children}</main>
    </div>
  );
}

export function Panel({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="mb-6 flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-stone-950">{title}</h2>
        {description ? <p className="text-sm leading-6 text-stone-600">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
